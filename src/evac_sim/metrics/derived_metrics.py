from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DerivedMetricPaths:
    density_metrics: Path
    evacuation_metrics: Path
    comparison_metrics: Path


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _read_table(conn: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    if not _table_exists(conn, table_name):
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    data = pd.DataFrame({"value": values, "weight": weights}).dropna()
    data = data[data["weight"] > 0]

    if data.empty:
        return float("nan")

    return float((data["value"] * data["weight"]).sum() / data["weight"].sum())


def _safe_quantile(values: pd.Series, q: float) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return float("nan")
    return float(clean.quantile(q))


def compute_density_metrics(
    conn: sqlite3.Connection,
    *,
    metrics_config: dict[str, Any],
) -> pd.DataFrame:
    cfg = metrics_config.get("density", {})

    if not cfg.get("enabled", True):
        return pd.DataFrame()

    table_name = cfg.get("source_table", "agent_area_data")
    agent_area = _read_table(conn, table_name)

    if agent_area.empty:
        return pd.DataFrame()

    required = {"frame", "agent_id", "area"}
    missing = required - set(agent_area.columns)

    if missing:
        raise ValueError(
            f"Table {table_name!r} is missing required columns: {sorted(missing)}"
        )

    sample_every = int(cfg.get("sample_every_frames", 25) or 1)
    high_threshold = float(cfg.get("high_density_threshold", 10))

    df = agent_area.copy()
    df["frame"] = pd.to_numeric(df["frame"], errors="coerce")
    df = df.dropna(subset=["frame", "agent_id", "area"])
    df["frame"] = df["frame"].astype(int)

    if sample_every > 1:
        df = df[df["frame"] % sample_every == 0]

    if df.empty:
        return pd.DataFrame()

    group_cols = []
    for column in ("case_name", "mode"):
        if column in df.columns:
            group_cols.append(column)

    density_by_area_frame = (
        df.groupby([*group_cols, "frame", "area"], dropna=False)["agent_id"]
        .nunique()
        .reset_index(name="area_density")
    )

    exposure = df.merge(
        density_by_area_frame,
        on=[*group_cols, "frame", "area"],
        how="left",
    )

    high_density_records = exposure["area_density"] >= high_threshold

    rows: list[dict[str, Any]] = []
    grouped_exposure = exposure.groupby(group_cols, dropna=False) if group_cols else [((), exposure)]

    for group_key, group_df in grouped_exposure:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        row = {column: value for column, value in zip(group_cols, group_key)}

        area_frame_filter = pd.Series(True, index=density_by_area_frame.index)
        for column, value in row.items():
            area_frame_filter &= density_by_area_frame[column] == value
        area_frame_df = density_by_area_frame[area_frame_filter]

        density = pd.to_numeric(group_df["area_density"], errors="coerce")
        area_density = pd.to_numeric(area_frame_df["area_density"], errors="coerce")

        high_agent_ratio = float((density >= high_threshold).mean()) if not density.empty else float("nan")
        high_frame_ratio = float((area_density >= high_threshold).mean()) if not area_density.empty else float("nan")

        row.update(
            {
                "sample_every_frames": sample_every,
                "high_density_threshold": high_threshold,
                "sampled_agent_records": int(len(group_df)),
                "sampled_frames": int(group_df["frame"].nunique()),
                "sampled_areas": int(group_df["area"].nunique()),
                "avg_area_density": float(area_density.mean()) if not area_density.empty else float("nan"),
                "p90_area_density": _safe_quantile(area_density, 0.90),
                "peak_area_density": float(area_density.max()) if not area_density.empty else float("nan"),
                "avg_density_exposure": float(density.mean()) if not density.empty else float("nan"),
                "p90_density_exposure": _safe_quantile(density, 0.90),
                "max_density_exposure": float(density.max()) if not density.empty else float("nan"),
                "high_density_agent_ratio": high_agent_ratio,
                "high_density_frame_ratio": high_frame_ratio,
            }
        )

        score_metric = str(cfg.get("congestion_score_metric", "p90_density_exposure"))
        row["congestion_density_score"] = row.get(score_metric, row["p90_density_exposure"])

        rows.append(row)

    return pd.DataFrame(rows)


def compute_evacuation_metrics(
    conn: sqlite3.Connection,
    *,
    metrics_config: dict[str, Any],
) -> pd.DataFrame:
    cfg = metrics_config.get("evacuation", {})

    if not cfg.get("enabled", True):
        return pd.DataFrame()

    table_name = cfg.get("source_table", "experiment_metrics")
    metrics = _read_table(conn, table_name)

    if metrics.empty:
        return pd.DataFrame()

    weight_col = cfg.get("weight_column", "n_records")
    if weight_col not in metrics.columns:
        metrics[weight_col] = 1.0

    metrics[weight_col] = pd.to_numeric(metrics[weight_col], errors="coerce").fillna(1.0)

    time_columns = cfg.get("time_columns", {}) or {}
    column_map = {
        "min_evac_time": time_columns.get("min", "min_time"),
        "avg_evac_time": time_columns.get("avg", "avg_time"),
        "median_evac_time": time_columns.get("median", "median_time"),
        "p90_evac_time": time_columns.get("p90", "p90_time"),
        "max_evac_time": time_columns.get("max", "max_time"),
    }

    group_cols = []
    for column in ("case_name", "algorithm", "awareness"):
        if column in metrics.columns:
            group_cols.append(column)

    rows: list[dict[str, Any]] = []
    grouped = metrics.groupby(group_cols, dropna=False) if group_cols else [((), metrics)]

    for group_key, group_df in grouped:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        row = {column: value for column, value in zip(group_cols, group_key)}
        row["groups"] = int(len(group_df))
        row["total_n_records"] = float(group_df[weight_col].sum())

        for output_name, source_col in column_map.items():
            if source_col not in group_df.columns:
                row[output_name] = float("nan")
                continue
            row[output_name] = _weighted_mean(
                pd.to_numeric(group_df[source_col], errors="coerce"),
                group_df[weight_col],
            )

        if "agent_group_id" in group_df.columns:
            row["distinct_groups"] = int(group_df["agent_group_id"].nunique())

        rows.append(row)

    return pd.DataFrame(rows)


def compute_route_metrics(
    conn: sqlite3.Connection,
    *,
    metrics_config: dict[str, Any],
) -> pd.DataFrame:
    cfg = metrics_config.get("route", {})

    if not cfg.get("enabled", True):
        return pd.DataFrame()

    table_name = cfg.get("source_table", "experiment_metrics")
    metrics = _read_table(conn, table_name)

    if metrics.empty:
        return pd.DataFrame()

    cost_col = cfg.get("avg_path_cost_column", "avg_path_cost")
    weight_col = metrics_config.get("evacuation", {}).get("weight_column", "n_records")

    if cost_col not in metrics.columns:
        return pd.DataFrame()

    if weight_col not in metrics.columns:
        metrics[weight_col] = 1.0

    group_cols = []
    for column in ("case_name", "algorithm", "awareness"):
        if column in metrics.columns:
            group_cols.append(column)

    rows: list[dict[str, Any]] = []
    grouped = metrics.groupby(group_cols, dropna=False) if group_cols else [((), metrics)]

    for group_key, group_df in grouped:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)

        row = {column: value for column, value in zip(group_cols, group_key)}
        row["avg_path_cost"] = _weighted_mean(
            pd.to_numeric(group_df[cost_col], errors="coerce"),
            pd.to_numeric(group_df[weight_col], errors="coerce").fillna(1.0),
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _merge_metric_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [frame for frame in frames if frame is not None and not frame.empty]

    if not non_empty:
        return pd.DataFrame()

    merged = non_empty[0].copy()

    for frame in non_empty[1:]:
        common_keys = [
            key
            for key in ("case_name", "mode", "algorithm", "awareness")
            if key in merged.columns and key in frame.columns
        ]

        if not common_keys:
            merged = merged.join(frame, how="outer", rsuffix="_extra")
        else:
            merged = merged.merge(frame, on=common_keys, how="outer")

    return merged


def build_derived_metrics_for_db(
    db_path: Path,
    *,
    metrics_config: dict[str, Any],
    output_dir: Path | None = None,
) -> DerivedMetricPaths:
    if not db_path.exists():
        raise FileNotFoundError(f"Simulation database not found: {db_path}")

    if output_dir is None:
        output_dir = db_path.parents[1] / "csv"

    output_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        density = compute_density_metrics(conn, metrics_config=metrics_config)
        evacuation = compute_evacuation_metrics(conn, metrics_config=metrics_config)
        route = compute_route_metrics(conn, metrics_config=metrics_config)

    density_path = output_dir / "density_metrics.csv"
    evacuation_path = output_dir / "evacuation_metrics.csv"
    comparison_path = output_dir / "comparison_metrics.csv"

    outputs_cfg = metrics_config.get("outputs", {})

    if outputs_cfg.get("write_density_metrics", True):
        density.to_csv(density_path, index=False)

    if outputs_cfg.get("write_evacuations_metrics", True):
        evacuation.to_csv(evacuation_path, index=False)

    comparison = _merge_metric_frames([evacuation, density, route])

    if outputs_cfg.get("write_comparison_metrics", True):
        comparison.to_csv(comparison_path, index=False)

    return DerivedMetricPaths(
        density_metrics=density_path,
        evacuation_metrics=evacuation_path,
        comparison_metrics=comparison_path,
    )
