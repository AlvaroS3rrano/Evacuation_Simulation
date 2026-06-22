from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

METRICS = {
    "avg_evac_time": "Average evacuation time",
    "median_evac_time": "Median evacuation time",
    "p90_evac_time": "P90 evacuation time",
    "max_evac_time": "Maximum evacuation time",
    "avg_density_exposure": "Average density exposure",
    "p90_density_exposure": "P90 density exposure",
    "peak_area_density": "Peak area density",
    "high_density_agent_ratio": "High density agent ratio",
    "congestion_density_score": "Congestion density score",
    "avg_path_cost": "Average path cost",
}

# Lower is better for all these metrics.
COMPOSITE_WEIGHTS = {
    "avg_evac_time": 0.35,
    "p90_evac_time": 0.20,
    "max_evac_time": 0.10,
    "avg_density_exposure": 0.15,
    "high_density_agent_ratio": 0.10,
    "avg_path_cost": 0.10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate congestion heuristic comparison metrics by scenario "
            "instead of by individual simulation case."
        )
    )

    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/congestion_heuristics_efficient_high"),
        help=(
            "Root folder containing heuristic result folders. "
            "Default: runs/congestion_heuristics_efficient_high"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output folder. Default: <run-root>/comparison/scenario_strategy"
        ),
    )

    parser.add_argument(
        "--exclude-base",
        action="store_true",
        help=(
            "Exclude base_* cases from scenario-level statistics. "
            "Useful if you want variance only across random cases."
        ),
    )

    parser.add_argument(
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic for percentage comparisons. Default: none.",
    )

    return parser.parse_args()


def scenario_from_case_id(case_id: str) -> str:
    if case_id.startswith("base_"):
        return case_id.removeprefix("base_")

    if case_id.startswith("random_"):
        body = case_id.removeprefix("random_")
        body = re.sub(r"_\d+$", "", body)
        return body

    return case_id


def is_base_case(case_id: str) -> bool:
    return case_id.startswith("base_")


def discover_metric_files(run_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for heuristic_dir in sorted(run_root.iterdir()):
        if not heuristic_dir.is_dir():
            continue

        heuristic = heuristic_dir.name

        if heuristic not in HEURISTIC_ORDER:
            continue

        for csv_path in sorted(
            heuristic_dir.glob("*/artifacts/csv/comparison_metrics.csv")
        ):
            case_id = csv_path.parents[2].name

            rows.append(
                {
                    "case_id": case_id,
                    "scenario": scenario_from_case_id(case_id),
                    "heuristic": heuristic,
                    "metrics_path": csv_path,
                }
            )

    return rows


def find_metric_column(df: pd.DataFrame, metric: str) -> str | None:
    candidates = [
        f"{metric}_weighted",
        metric,
    ]

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    return None


def find_weight_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "n_records",
        "total_n_records",
        "records",
        "agent_count",
        "agents",
    ]

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    return None


def weighted_average(
    values: pd.Series,
    weights: pd.Series | None,
) -> float:
    values = pd.to_numeric(values, errors="coerce")

    if weights is None:
        return float(values.mean())

    weights = pd.to_numeric(weights, errors="coerce")

    valid = values.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        return float(values.mean())

    return float(np.average(values[valid], weights=weights[valid]))


def read_one_metrics_file(row: dict[str, Any]) -> dict[str, Any] | None:
    csv_path: Path = row["metrics_path"]

    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return None

    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return None

    if df.empty:
        return None

    weight_col = find_weight_column(df)
    weights = df[weight_col] if weight_col is not None else None

    if "group_id" in df.columns:
        groups = int(df["group_id"].nunique())
    elif "groups" in df.columns:
        groups = int(pd.to_numeric(df["groups"], errors="coerce").fillna(0).sum())
    else:
        groups = int(len(df))

    if weights is not None:
        total_n_records = float(
            pd.to_numeric(weights, errors="coerce").fillna(0).sum()
        )
    elif "total_n_records" in df.columns:
        total_n_records = float(
            pd.to_numeric(df["total_n_records"], errors="coerce").fillna(0).sum()
        )
    else:
        total_n_records = float(len(df))

    result = {
        "case_id": row["case_id"],
        "scenario": row["scenario"],
        "heuristic": row["heuristic"],
        "is_base_case": is_base_case(row["case_id"]),
        "groups": groups,
        "total_n_records": total_n_records,
        "metrics_path": str(csv_path),
    }

    for metric in METRICS:
        col = find_metric_column(df, metric)

        if col is None:
            result[metric] = np.nan
            continue

        result[metric] = weighted_average(df[col], weights)

    return result


def build_case_metric_table(
    metric_files: list[dict[str, Any]],
    *,
    exclude_base: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for metric_file in metric_files:
        if exclude_base and is_base_case(metric_file["case_id"]):
            continue

        row = read_one_metrics_file(metric_file)

        if row is not None:
            rows.append(row)

    if not rows:
        raise RuntimeError(
            "No comparison_metrics.csv files could be read. "
            "Check --run-root and that compare has been executed first."
        )

    return pd.DataFrame(rows)


def to_long_metrics(case_metrics: pd.DataFrame) -> pd.DataFrame:
    id_columns = [
        "case_id",
        "scenario",
        "heuristic",
        "is_base_case",
        "groups",
        "total_n_records",
        "metrics_path",
    ]

    value_columns = [
        metric
        for metric in METRICS
        if metric in case_metrics.columns
    ]

    long_df = case_metrics.melt(
        id_vars=id_columns,
        value_vars=value_columns,
        var_name="metric",
        value_name="value",
    )

    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")
    long_df = long_df.dropna(subset=["value"])

    return long_df


def weighted_mean_by_records(group: pd.DataFrame) -> float:
    values = pd.to_numeric(group["value"], errors="coerce")
    weights = pd.to_numeric(group["total_n_records"], errors="coerce").fillna(0)

    valid = values.notna() & (weights > 0)

    if not valid.any():
        return float(values.mean())

    return float(np.average(values[valid], weights=weights[valid]))


def build_scenario_metric_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        long_df
        .groupby(["scenario", "heuristic", "metric"], as_index=False)
        .agg(
            n_cases=("case_id", "nunique"),
            mean=("value", "mean"),
            std=("value", "std"),
            var=("value", "var"),
            median=("value", "median"),
            min=("value", "min"),
            max=("value", "max"),
            q25=("value", lambda s: float(s.quantile(0.25))),
            q75=("value", lambda s: float(s.quantile(0.75))),
        )
    )

    summary["std"] = summary["std"].fillna(0.0)
    summary["var"] = summary["var"].fillna(0.0)
    summary["iqr"] = summary["q75"] - summary["q25"]

    summary["cv_pct"] = np.where(
        summary["mean"].abs() > 0,
        100.0 * summary["std"] / summary["mean"].abs(),
        np.nan,
    )

    weighted = (
        long_df
        .groupby(["scenario", "heuristic", "metric"])
        .apply(weighted_mean_by_records, include_groups=False)
        .reset_index(name="weighted_mean_by_records")
    )

    summary = summary.merge(
        weighted,
        on=["scenario", "heuristic", "metric"],
        how="left",
    )

    return summary


def build_delta_vs_baseline(
    long_df: pd.DataFrame,
    *,
    baseline: str,
) -> pd.DataFrame:
    baseline_df = (
        long_df[long_df["heuristic"] == baseline]
        [["scenario", "case_id", "metric", "value"]]
        .rename(columns={"value": "baseline_value"})
    )

    merged = long_df.merge(
        baseline_df,
        on=["scenario", "case_id", "metric"],
        how="inner",
    )

    merged = merged[merged["heuristic"] != baseline].copy()

    merged["delta_abs_vs_baseline"] = (
        merged["value"] - merged["baseline_value"]
    )

    merged["delta_pct_vs_baseline"] = np.where(
        merged["baseline_value"].abs() > 0,
        100.0 * merged["delta_abs_vs_baseline"] / merged["baseline_value"],
        np.nan,
    )

    # Lower is better for all selected metrics.
    merged["wins_vs_baseline"] = merged["delta_abs_vs_baseline"] < 0

    delta_summary = (
        merged
        .groupby(["scenario", "heuristic", "metric"], as_index=False)
        .agg(
            n_cases=("case_id", "nunique"),
            delta_abs_mean=("delta_abs_vs_baseline", "mean"),
            delta_abs_std=("delta_abs_vs_baseline", "std"),
            delta_abs_var=("delta_abs_vs_baseline", "var"),
            delta_pct_mean=("delta_pct_vs_baseline", "mean"),
            delta_pct_std=("delta_pct_vs_baseline", "std"),
            delta_pct_var=("delta_pct_vs_baseline", "var"),
            wins_vs_baseline=("wins_vs_baseline", "sum"),
        )
    )

    delta_summary["delta_abs_std"] = delta_summary["delta_abs_std"].fillna(0.0)
    delta_summary["delta_abs_var"] = delta_summary["delta_abs_var"].fillna(0.0)
    delta_summary["delta_pct_std"] = delta_summary["delta_pct_std"].fillna(0.0)
    delta_summary["delta_pct_var"] = delta_summary["delta_pct_var"].fillna(0.0)

    delta_summary["win_rate_vs_baseline_pct"] = np.where(
        delta_summary["n_cases"] > 0,
        100.0 * delta_summary["wins_vs_baseline"] / delta_summary["n_cases"],
        np.nan,
    )

    return delta_summary


def build_best_counts(long_df: pd.DataFrame) -> pd.DataFrame:
    # Lower is better for all metrics.
    best_idx = (
        long_df
        .groupby(["scenario", "case_id", "metric"])["value"]
        .idxmin()
    )

    best_rows = long_df.loc[best_idx].copy()

    best_counts = (
        best_rows
        .groupby(["scenario", "heuristic", "metric"], as_index=False)
        .agg(best_case_count=("case_id", "nunique"))
    )

    total_cases = (
        long_df
        .groupby(["scenario", "metric"], as_index=False)
        .agg(total_cases=("case_id", "nunique"))
    )

    best_counts = best_counts.merge(
        total_cases,
        on=["scenario", "metric"],
        how="left",
    )

    best_counts["best_case_rate_pct"] = np.where(
        best_counts["total_cases"] > 0,
        100.0 * best_counts["best_case_count"] / best_counts["total_cases"],
        np.nan,
    )

    return best_counts


def build_composite_scores(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    composite_input = long_df[
        long_df["metric"].isin(COMPOSITE_WEIGHTS)
    ].copy()

    composite_input["weight"] = composite_input["metric"].map(COMPOSITE_WEIGHTS)

    normalized_parts: list[pd.DataFrame] = []

    for (_, _, metric), group in composite_input.groupby(
        ["scenario", "case_id", "metric"]
    ):
        group = group.copy()

        min_value = group["value"].min()
        max_value = group["value"].max()

        if math.isclose(float(max_value), float(min_value)):
            group["normalized_score"] = 0.0
        else:
            # Lower is better.
            group["normalized_score"] = (
                (group["value"] - min_value) / (max_value - min_value)
            )

        normalized_parts.append(group)

    normalized = pd.concat(normalized_parts, ignore_index=True)

    case_scores = (
        normalized
        .groupby(["scenario", "case_id", "heuristic"], as_index=False)
        .apply(
            lambda g: pd.Series(
                {
                    "composite_score": float(
                        np.average(
                            g["normalized_score"],
                            weights=g["weight"],
                        )
                    ),
                    "metrics_used": int(g["metric"].nunique()),
                }
            ),
            include_groups=False,
        )
    )

    summary = (
        case_scores
        .groupby(["scenario", "heuristic"], as_index=False)
        .agg(
            n_cases=("case_id", "nunique"),
            composite_mean=("composite_score", "mean"),
            composite_std=("composite_score", "std"),
            composite_var=("composite_score", "var"),
            composite_median=("composite_score", "median"),
            composite_min=("composite_score", "min"),
            composite_max=("composite_score", "max"),
        )
    )

    summary["composite_std"] = summary["composite_std"].fillna(0.0)
    summary["composite_var"] = summary["composite_var"].fillna(0.0)

    summary["rank"] = (
        summary
        .sort_values(["scenario", "composite_mean"])
        .groupby("scenario")
        .cumcount()
        + 1
    )

    return case_scores, summary


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No data available._"

    display = df.copy()

    for col in display.columns:
        if pd.api.types.is_numeric_dtype(display[col]):
            display[col] = display[col].map(
                lambda x: "" if pd.isna(x) else round(float(x), 4)
            )

    try:
        return display.to_markdown(index=False)
    except Exception:
        headers = list(display.columns)
        rows = display.astype(str).values.tolist()

        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]

        for row in rows:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)


def write_report(
    *,
    output_path: Path,
    scenario_metric_summary: pd.DataFrame,
    delta_summary: pd.DataFrame,
    best_counts: pd.DataFrame,
    composite_summary: pd.DataFrame,
    baseline: str,
    exclude_base: bool,
) -> None:
    lines: list[str] = []

    lines.append("# Scenario-level congestion heuristic comparison")
    lines.append("")
    lines.append(
        "This report aggregates all cases belonging to the same scenario. "
        "Each case is treated as one scenario observation."
    )
    lines.append("")
    lines.append(f"Baseline heuristic: `{baseline}`")
    lines.append(f"Base cases excluded: `{exclude_base}`")
    lines.append("")
    lines.append("Composite score interpretation: lower is better.")
    lines.append("")
    lines.append("Composite score weights:")
    lines.append("")
    for metric, weight in COMPOSITE_WEIGHTS.items():
        lines.append(f"- `{metric}`: {weight}")
    lines.append("")

    lines.append("## Best strategy by scenario")
    lines.append("")

    best_composite = (
        composite_summary
        .sort_values(["scenario", "composite_mean"])
        .groupby("scenario")
        .head(1)
        [[
            "scenario",
            "heuristic",
            "n_cases",
            "composite_mean",
            "composite_std",
            "composite_var",
        ]]
        .rename(columns={"heuristic": "best_composite_heuristic"})
    )

    lines.append(markdown_table(best_composite))
    lines.append("")

    key_metrics = [
        "avg_evac_time",
        "p90_evac_time",
        "max_evac_time",
        "avg_density_exposure",
        "high_density_agent_ratio",
        "avg_path_cost",
    ]

    for scenario in sorted(scenario_metric_summary["scenario"].unique()):
        lines.append(f"## Scenario: `{scenario}`")
        lines.append("")

        comp = (
            composite_summary[composite_summary["scenario"] == scenario]
            .sort_values("composite_mean")
            [[
                "rank",
                "heuristic",
                "n_cases",
                "composite_mean",
                "composite_std",
                "composite_var",
                "composite_median",
                "composite_min",
                "composite_max",
            ]]
        )

        lines.append("### Composite ranking")
        lines.append("")
        lines.append(markdown_table(comp))
        lines.append("")

        for metric in key_metrics:
            metric_summary = scenario_metric_summary[
                (scenario_metric_summary["scenario"] == scenario)
                & (scenario_metric_summary["metric"] == metric)
            ].copy()

            metric_delta = delta_summary[
                (delta_summary["scenario"] == scenario)
                & (delta_summary["metric"] == metric)
            ][
                [
                    "heuristic",
                    "delta_pct_mean",
                    "delta_pct_std",
                    "delta_pct_var",
                    "win_rate_vs_baseline_pct",
                ]
            ]

            metric_best = best_counts[
                (best_counts["scenario"] == scenario)
                & (best_counts["metric"] == metric)
            ][
                [
                    "heuristic",
                    "best_case_count",
                    "best_case_rate_pct",
                ]
            ]

            table = metric_summary.merge(
                metric_delta,
                on="heuristic",
                how="left",
            ).merge(
                metric_best,
                on="heuristic",
                how="left",
            )

            table["heuristic"] = pd.Categorical(
                table["heuristic"],
                categories=HEURISTIC_ORDER,
                ordered=True,
            )

            table = table.sort_values("heuristic")

            table = table[
                [
                    "heuristic",
                    "n_cases",
                    "mean",
                    "std",
                    "var",
                    "cv_pct",
                    "median",
                    "min",
                    "max",
                    "weighted_mean_by_records",
                    "delta_pct_mean",
                    "delta_pct_std",
                    "win_rate_vs_baseline_pct",
                    "best_case_count",
                    "best_case_rate_pct",
                ]
            ]

            lines.append(f"### Metric: `{metric}`")
            lines.append("")
            lines.append(markdown_table(table))
            lines.append("")

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    run_root = args.run_root.resolve()

    if not run_root.exists():
        raise FileNotFoundError(f"Run root does not exist: {run_root}")

    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else run_root / "comparison" / "scenario_strategy"
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    metric_files = discover_metric_files(run_root)

    if not metric_files:
        raise RuntimeError(
            f"No comparison_metrics.csv files found under {run_root}"
        )

    case_metrics = build_case_metric_table(
        metric_files,
        exclude_base=args.exclude_base,
    )

    long_df = to_long_metrics(case_metrics)

    scenario_metric_summary = build_scenario_metric_summary(long_df)

    delta_summary = build_delta_vs_baseline(
        long_df,
        baseline=args.baseline,
    )

    best_counts = build_best_counts(long_df)

    case_composite_scores, composite_summary = build_composite_scores(long_df)

    case_metrics.to_csv(
        output_dir / "scenario_case_metric_values.csv",
        index=False,
    )

    long_df.to_csv(
        output_dir / "scenario_case_metric_values_long.csv",
        index=False,
    )

    scenario_metric_summary.to_csv(
        output_dir / "scenario_metric_summary.csv",
        index=False,
    )

    delta_summary.to_csv(
        output_dir / "scenario_delta_vs_baseline.csv",
        index=False,
    )

    best_counts.to_csv(
        output_dir / "scenario_best_counts.csv",
        index=False,
    )

    case_composite_scores.to_csv(
        output_dir / "scenario_case_composite_scores.csv",
        index=False,
    )

    composite_summary.to_csv(
        output_dir / "scenario_composite_summary.csv",
        index=False,
    )

    report_path = output_dir / "scenario_strategy_report.md"

    write_report(
        output_path=report_path,
        scenario_metric_summary=scenario_metric_summary,
        delta_summary=delta_summary,
        best_counts=best_counts,
        composite_summary=composite_summary,
        baseline=args.baseline,
        exclude_base=args.exclude_base,
    )

    print()
    print("=" * 80)
    print("Scenario-level comparison generated")
    print("=" * 80)
    print(f"Run root: {run_root}")
    print(f"Output dir: {output_dir}")
    print(f"Report: {report_path}")
    print()
    print("Generated files:")
    print(f"- {output_dir / 'scenario_strategy_report.md'}")
    print(f"- {output_dir / 'scenario_metric_summary.csv'}")
    print(f"- {output_dir / 'scenario_delta_vs_baseline.csv'}")
    print(f"- {output_dir / 'scenario_best_counts.csv'}")
    print(f"- {output_dir / 'scenario_composite_summary.csv'}")
    print(f"- {output_dir / 'scenario_case_metric_values.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())