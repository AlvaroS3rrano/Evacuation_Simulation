from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs" / "congestion_heuristics_efficient_high"
DEFAULT_METRICS_CONFIG = PROJECT_ROOT / "configs" / "metrics" / "default_metrics.yaml"
DEFAULT_OUTPUT_DIR_NAME = "comparison"
HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

LEGACY_RENAME_MAP = {
    "avg_time": "avg_evac_time",
    "median_time": "median_evac_time",
    "p90_time": "p90_evac_time",
    "max_time": "max_evac_time",
    "min_time": "min_evac_time",
}

FALLBACK_MAIN_METRICS = [
    "avg_evac_time",
    "median_evac_time",
    "p90_evac_time",
    "max_evac_time",
    "avg_density_exposure",
    "p90_density_exposure",
    "peak_area_density",
    "high_density_agent_ratio",
    "congestion_density_score",
    "avg_path_cost",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare congestion heuristic results using configurable derived metrics."
    )
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--metrics-config", type=Path, default=DEFAULT_METRICS_CONFIG)
    parser.add_argument("--heuristics", nargs="+", default=HEURISTIC_ORDER, choices=HEURISTIC_ORDER)
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--baseline", default="none", choices=HEURISTIC_ORDER)
    parser.add_argument(
        "--metric",
        default=None,
        help="Main metric for compact terminal summary. Defaults to first configured metric.",
    )
    parser.add_argument(
        "--require-all-heuristics",
        action="store_true",
        help="Skip cases missing one of the selected heuristics.",
    )
    return parser.parse_args()


def load_metrics_config(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise FileNotFoundError(f"Metrics config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Metrics config must be a mapping: {path}")

    return data


def configured_main_metrics(metrics_config: dict[str, Any]) -> list[str]:
    metrics = (
        metrics_config
        .get("comparison", {})
        .get("main_metrics", FALLBACK_MAIN_METRICS)
    )

    return [str(metric) for metric in metrics]


def lower_is_better_map(metrics_config: dict[str, Any]) -> dict[str, bool]:
    raw = metrics_config.get("comparison", {}).get("lower_is_better", {}) or {}
    return {str(key): bool(value) for key, value in raw.items()}


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"WARNING: could not read {path}: {exc}", file=sys.stderr)
        return None


def discover_metric_files(
    *,
    runs_dir: Path,
    heuristics: list[str],
) -> list[tuple[str, str, Path, str]]:
    files: list[tuple[str, str, Path, str]] = []

    for heuristic in heuristics:
        heuristic_dir = runs_dir / heuristic

        if not heuristic_dir.exists():
            print(f"WARNING: heuristic directory not found: {heuristic_dir}", file=sys.stderr)
            continue

        for case_dir in sorted(path for path in heuristic_dir.iterdir() if path.is_dir()):
            comparison_path = case_dir / "artifacts" / "csv" / "comparison_metrics.csv"
            legacy_path = case_dir / "artifacts" / "csv" / "experiment_metrics.csv"

            if comparison_path.exists():
                files.append((heuristic, case_dir.name, comparison_path, "comparison_metrics"))
            elif legacy_path.exists():
                files.append((heuristic, case_dir.name, legacy_path, "experiment_metrics"))
            else:
                print(
                    f"WARNING: no metrics file found for {heuristic}/{case_dir.name}",
                    file=sys.stderr,
                )

    return files


def normalise_metric_frame(
    df: pd.DataFrame,
    *,
    heuristic: str,
    case_id: str,
    metrics_path: Path,
    source_type: str,
) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "heuristic", heuristic)
    df.insert(1, "case_id", case_id)
    df.insert(2, "metrics_source", source_type)
    df.insert(3, "metrics_path", str(metrics_path))

    for old, new in LEGACY_RENAME_MAP.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    if "n_records" in df.columns and "total_n_records" not in df.columns:
        df["total_n_records"] = pd.to_numeric(df["n_records"], errors="coerce")

    if "agent_group_id" in df.columns and "groups" not in df.columns:
        df["groups"] = 1

    if "case_name" in df.columns and "mode" not in df.columns:
        df["mode"] = df["case_name"].astype(str).str.extract(r"_mode_(\d+)$")[0]

    return df


def load_all_metrics(
    *,
    runs_dir: Path,
    heuristics: list[str],
    cases: list[str] | None,
) -> pd.DataFrame:
    metric_files = discover_metric_files(runs_dir=runs_dir, heuristics=heuristics)
    requested_cases = set(cases or [])
    frames: list[pd.DataFrame] = []

    for heuristic, case_id, metrics_path, source_type in metric_files:
        if requested_cases and case_id not in requested_cases:
            continue

        df = safe_read_csv(metrics_path)

        if df is None or df.empty:
            continue

        frames.append(
            normalise_metric_frame(
                df,
                heuristic=heuristic,
                case_id=case_id,
                metrics_path=metrics_path,
                source_type=source_type,
            )
        )

    if not frames:
        raise RuntimeError(f"No metrics files found under {runs_dir}")

    combined = pd.concat(frames, ignore_index=True)

    for column in combined.columns:
        if column in {"heuristic", "case_id", "metrics_source", "metrics_path", "case_name", "mode", "algorithm", "awareness"}:
            continue
        combined[column] = pd.to_numeric(combined[column], errors="ignore")

    return combined


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    clean = pd.DataFrame({"value": values, "weight": weights}).dropna()
    clean = clean[clean["weight"] > 0]

    if clean.empty:
        return float("nan")

    return float((clean["value"] * clean["weight"]).sum() / clean["weight"].sum())


def aggregate_case_heuristic(group: pd.DataFrame, metrics: list[str]) -> pd.Series:
    weights = (
        pd.to_numeric(group["total_n_records"], errors="coerce").fillna(1.0)
        if "total_n_records" in group.columns
        else pd.Series([1.0] * len(group), index=group.index)
    )

    result: dict[str, Any] = {
        "rows": int(len(group)),
        "groups": int(group["groups"].sum()) if "groups" in group.columns else int(len(group)),
        "total_n_records": float(weights.sum()),
        "metrics_source": ",".join(sorted(set(group["metrics_source"].astype(str)))),
    }

    for metric in metrics:
        if metric not in group.columns:
            continue

        values = pd.to_numeric(group[metric], errors="coerce")
        result[f"{metric}_mean"] = float(values.mean())
        result[f"{metric}_median"] = float(values.median())
        result[f"{metric}_weighted"] = weighted_mean(values, weights)

    return pd.Series(result)


def build_summary(combined: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    summary = (
        combined
        .groupby(["case_id", "heuristic"], dropna=False)
        .apply(lambda group: aggregate_case_heuristic(group, metrics), include_groups=False)
        .reset_index()
    )

    summary["heuristic"] = pd.Categorical(summary["heuristic"], categories=HEURISTIC_ORDER, ordered=True)
    return summary.sort_values(["case_id", "heuristic"]).reset_index(drop=True)


def percentage_delta(value: float, baseline: float) -> float:
    if pd.isna(value) or pd.isna(baseline):
        return float("nan")
    if math.isclose(float(baseline), 0.0):
        return float("nan")
    return float(((value - baseline) / baseline) * 100.0)


def build_comparison_vs_baseline(summary: pd.DataFrame, *, baseline: str) -> pd.DataFrame:
    metric_fields = [
        column
        for column in summary.columns
        if column.endswith("_weighted") or column.endswith("_mean") or column.endswith("_median")
    ]

    baseline_df = summary[summary["heuristic"] == baseline][["case_id", *metric_fields]].copy()
    baseline_df = baseline_df.rename(columns={column: f"{column}_baseline" for column in metric_fields})

    comparison = summary.merge(baseline_df, on="case_id", how="left")

    for metric_field in metric_fields:
        baseline_column = f"{metric_field}_baseline"
        comparison[f"{metric_field}_delta_vs_{baseline}"] = comparison[metric_field] - comparison[baseline_column]
        comparison[f"{metric_field}_pct_vs_{baseline}"] = comparison.apply(
            lambda row: percentage_delta(row[metric_field], row[baseline_column]),
            axis=1,
        )

    return comparison


def build_best_by_metric(
    summary: pd.DataFrame,
    *,
    metrics: list[str],
    lower_is_better: dict[str, bool],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for case_id, case_df in summary.groupby("case_id"):
        for metric in metrics:
            column = f"{metric}_weighted"

            if column not in case_df.columns:
                continue

            valid = case_df.dropna(subset=[column])

            if valid.empty:
                continue

            best = valid.sort_values(column, ascending=lower_is_better.get(metric, True)).iloc[0]
            rows.append(
                {
                    "case_id": case_id,
                    "metric": metric,
                    "best_heuristic": best["heuristic"],
                    "best_value": best[column],
                }
            )

    return pd.DataFrame(rows)


def validate_completeness(
    *,
    summary: pd.DataFrame,
    selected_heuristics: list[str],
    require_all_heuristics: bool,
) -> pd.DataFrame:
    expected = set(selected_heuristics)
    complete_cases: list[str] = []
    incomplete_cases: list[tuple[str, list[str]]] = []

    for case_id, case_df in summary.groupby("case_id"):
        present = set(case_df["heuristic"].astype(str))
        missing = sorted(expected - present)

        if missing:
            incomplete_cases.append((case_id, missing))
        else:
            complete_cases.append(case_id)

    if incomplete_cases:
        print("Incomplete cases:")
        for case_id, missing in incomplete_cases:
            print(f"  - {case_id}: missing {', '.join(missing)}")
        print()

    if require_all_heuristics:
        return summary[summary["case_id"].isin(complete_cases)].copy()

    return summary


def write_markdown_report(
    *,
    out_dir: Path,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metrics: list[str],
    main_metric: str,
    baseline: str,
) -> Path:
    report_path = out_dir / "comparison_report.md"
    main_column = f"{main_metric}_weighted"
    pct_column = f"{main_column}_pct_vs_{baseline}"

    lines: list[str] = []
    lines.append("# Congestion heuristic comparison")
    lines.append("")
    lines.append(f"Main metric: `{main_column}`")
    lines.append(f"Baseline: `{baseline}`")
    lines.append("")
    lines.append("## Summary by case")
    lines.append("")

    for case_id, case_df in summary.groupby("case_id"):
        lines.append(f"### {case_id}")
        lines.append("")

        compact_columns = ["heuristic", "groups", "total_n_records", "metrics_source"]
        for metric in metrics:
            column = f"{metric}_weighted"
            if column in case_df.columns:
                compact_columns.append(column)

        compact = case_df[[column for column in compact_columns if column in case_df.columns]].copy()
        lines.append(compact.to_markdown(index=False))
        lines.append("")

        case_comp = comparison[comparison["case_id"] == case_id]
        if main_column in case_comp.columns and pct_column in case_comp.columns:
            deltas = case_comp[["heuristic", main_column, pct_column]].copy()
            lines.append(f"Change in `{main_metric}` vs `{baseline}`:")
            lines.append("")
            lines.append(deltas.to_markdown(index=False))
            lines.append("")

    lines.append("## Best heuristic by metric")
    lines.append("")
    lines.append(best_by_metric.to_markdown(index=False) if not best_by_metric.empty else "_No best-metric data available._")
    lines.append("")

    lines.append("## Input metric files")
    lines.append("")
    input_files = combined[["case_id", "heuristic", "metrics_source", "metrics_path"]].drop_duplicates()
    lines.append(input_files.to_markdown(index=False))
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_outputs(
    *,
    out_dir: Path,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metrics: list[str],
    main_metric: str,
    baseline: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_dir / "combined_metrics.csv", index=False)
    summary.to_csv(out_dir / "summary_by_case_heuristic.csv", index=False)
    comparison.to_csv(out_dir / "comparison_vs_baseline.csv", index=False)
    best_by_metric.to_csv(out_dir / "best_by_metric.csv", index=False)

    report = write_markdown_report(
        out_dir=out_dir,
        combined=combined,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        metrics=metrics,
        main_metric=main_metric,
        baseline=baseline,
    )

    print(f"Report written to: {report}")


def main() -> int:
    args = parse_args()
    runs_dir = args.runs_dir.resolve()
    out_dir = args.out_dir or runs_dir / DEFAULT_OUTPUT_DIR_NAME
    metrics_config = load_metrics_config(args.metrics_config)
    metrics = configured_main_metrics(metrics_config)
    main_metric = args.metric or metrics[0]

    if main_metric not in metrics:
        metrics = [main_metric, *metrics]

    combined = load_all_metrics(runs_dir=runs_dir, heuristics=args.heuristics, cases=args.cases)
    summary = build_summary(combined, metrics)
    summary = validate_completeness(
        summary=summary,
        selected_heuristics=args.heuristics,
        require_all_heuristics=args.require_all_heuristics,
    )
    comparison = build_comparison_vs_baseline(summary, baseline=args.baseline)
    best_by_metric = build_best_by_metric(
        summary,
        metrics=metrics,
        lower_is_better=lower_is_better_map(metrics_config),
    )

    write_outputs(
        out_dir=out_dir,
        combined=combined,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        metrics=metrics,
        main_metric=main_metric,
        baseline=args.baseline,
    )

    print()
    print("Comparison finished.")
    print(f"Output directory: {out_dir}")
    print(f"Main metric: {main_metric}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
