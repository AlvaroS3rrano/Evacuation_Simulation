from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs" / "congestion_heuristics_efficient_high"
DEFAULT_OUTPUT_DIR_NAME = "comparison"

HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

METRIC_COLUMNS = [
    "avg_time",
    "median_time",
    "p90_time",
    "min_time",
    "max_time",
    "avg_path_cost",
    "mean_remaining_path_risk",
    "remaining_path_risk_var",
    "cumulative_risk_exposure",
]

LOWER_IS_BETTER = {
    "avg_time": True,
    "median_time": True,
    "p90_time": True,
    "min_time": True,
    "max_time": True,
    "avg_path_cost": True,
    "mean_remaining_path_risk": True,
    "remaining_path_risk_var": True,
    "cumulative_risk_exposure": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare congestion heuristic results across cases."
    )

    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=(
            "Base directory produced by tools/run_all_congestion_heuristics.py. "
            f"Default: {DEFAULT_RUNS_DIR}"
        ),
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "Output directory for comparison CSV/Markdown files. "
            "Default: <runs-dir>/comparison"
        ),
    )

    parser.add_argument(
        "--heuristics",
        nargs="+",
        default=HEURISTIC_ORDER,
        choices=HEURISTIC_ORDER,
        help="Heuristics to compare.",
    )

    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional list of case ids to compare. If omitted, all cases found are used.",
    )

    parser.add_argument(
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic used for delta calculations.",
    )

    parser.add_argument(
        "--metric",
        default="avg_time",
        choices=METRIC_COLUMNS,
        help="Main metric used in the compact report.",
    )

    parser.add_argument(
        "--require-all-heuristics",
        action="store_true",
        help="Skip cases that do not have results for all selected heuristics.",
    )

    return parser.parse_args()


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
) -> list[tuple[str, str, Path]]:
    metric_files: list[tuple[str, str, Path]] = []

    for heuristic in heuristics:
        heuristic_dir = runs_dir / heuristic

        if not heuristic_dir.exists():
            print(
                f"WARNING: heuristic directory not found: {heuristic_dir}",
                file=sys.stderr,
            )
            continue

        for case_dir in sorted(p for p in heuristic_dir.iterdir() if p.is_dir()):
            metrics_path = case_dir / "artifacts" / "csv" / "experiment_metrics.csv"

            if metrics_path.exists():
                metric_files.append(
                    (
                        heuristic,
                        case_dir.name,
                        metrics_path,
                    )
                )
            else:
                print(
                    f"WARNING: metrics file not found: {metrics_path}",
                    file=sys.stderr,
                )

    return metric_files


def load_all_group_metrics(
    *,
    runs_dir: Path,
    heuristics: list[str],
    cases: list[str] | None,
) -> pd.DataFrame:
    metric_files = discover_metric_files(
        runs_dir=runs_dir,
        heuristics=heuristics,
    )

    frames: list[pd.DataFrame] = []

    requested_cases = set(cases or [])

    for heuristic, case_id, metrics_path in metric_files:
        if requested_cases and case_id not in requested_cases:
            continue

        df = safe_read_csv(metrics_path)

        if df is None or df.empty:
            continue

        df = df.copy()
        df.insert(0, "heuristic", heuristic)
        df.insert(1, "case_id", case_id)
        df.insert(2, "metrics_path", str(metrics_path))

        if "case_name" in df.columns:
            df["mode"] = df["case_name"].astype(str).str.extract(
                r"_mode_(\d+)$"
            )[0]
        else:
            df["mode"] = None

        frames.append(df)

    if not frames:
        raise RuntimeError(
            f"No experiment_metrics.csv files found under {runs_dir}"
        )

    combined = pd.concat(frames, ignore_index=True)

    for column in METRIC_COLUMNS + ["n_records"]:
        if column in combined.columns:
            combined[column] = pd.to_numeric(combined[column], errors="coerce")

    return combined


def weighted_mean(
    values: pd.Series,
    weights: pd.Series,
) -> float:
    clean = pd.DataFrame(
        {
            "value": values,
            "weight": weights,
        }
    ).dropna()

    clean = clean[clean["weight"] > 0]

    if clean.empty:
        return float("nan")

    return float((clean["value"] * clean["weight"]).sum() / clean["weight"].sum())


def aggregate_case_heuristic(group: pd.DataFrame) -> pd.Series:
    weights = group["n_records"] if "n_records" in group.columns else pd.Series(
        [1.0] * len(group),
        index=group.index,
    )

    result: dict[str, Any] = {
        "groups": int(len(group)),
        "total_n_records": float(group["n_records"].sum())
        if "n_records" in group.columns
        else float(len(group)),
    }

    for metric in METRIC_COLUMNS:
        if metric not in group.columns:
            continue

        result[f"{metric}_mean"] = float(group[metric].mean())
        result[f"{metric}_median"] = float(group[metric].median())
        result[f"{metric}_weighted"] = weighted_mean(group[metric], weights)

    return pd.Series(result)


def build_summary(combined: pd.DataFrame) -> pd.DataFrame:
    summary = (
        combined
        .groupby(["case_id", "heuristic"], dropna=False)
        .apply(aggregate_case_heuristic, include_groups=False)
        .reset_index()
    )

    summary["heuristic"] = pd.Categorical(
        summary["heuristic"],
        categories=HEURISTIC_ORDER,
        ordered=True,
    )

    return summary.sort_values(["case_id", "heuristic"]).reset_index(drop=True)


def build_comparison_vs_baseline(
    summary: pd.DataFrame,
    *,
    baseline: str,
) -> pd.DataFrame:
    metric_fields = [
        column
        for column in summary.columns
        if column.endswith("_weighted") or column.endswith("_mean")
    ]

    baseline_df = summary[summary["heuristic"] == baseline][
        ["case_id", *metric_fields]
    ].copy()

    rename_map = {
        column: f"{column}_baseline"
        for column in metric_fields
    }

    baseline_df = baseline_df.rename(columns=rename_map)

    comparison = summary.merge(
        baseline_df,
        on="case_id",
        how="left",
    )

    for metric_field in metric_fields:
        baseline_column = f"{metric_field}_baseline"
        delta_column = f"{metric_field}_delta_vs_{baseline}"
        pct_column = f"{metric_field}_pct_vs_{baseline}"

        comparison[delta_column] = (
            comparison[metric_field] - comparison[baseline_column]
        )

        comparison[pct_column] = comparison.apply(
            lambda row: percentage_delta(
                row[metric_field],
                row[baseline_column],
            ),
            axis=1,
        )

    return comparison


def percentage_delta(
    value: float,
    baseline: float,
) -> float:
    if baseline is None:
        return float("nan")

    if pd.isna(value) or pd.isna(baseline):
        return float("nan")

    if math.isclose(float(baseline), 0.0):
        return float("nan")

    return float(((value - baseline) / baseline) * 100.0)


def build_best_by_metric(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for case_id, case_df in summary.groupby("case_id"):
        for metric in METRIC_COLUMNS:
            weighted_column = f"{metric}_weighted"

            if weighted_column not in case_df.columns:
                continue

            valid = case_df.dropna(subset=[weighted_column])

            if valid.empty:
                continue

            ascending = LOWER_IS_BETTER.get(metric, True)

            best_row = valid.sort_values(
                weighted_column,
                ascending=ascending,
            ).iloc[0]

            rows.append(
                {
                    "case_id": case_id,
                    "metric": metric,
                    "best_heuristic": best_row["heuristic"],
                    "best_value": best_row[weighted_column],
                }
            )

    return pd.DataFrame(rows)


def build_wide_table(
    summary: pd.DataFrame,
    *,
    metric: str,
    aggregation: str = "weighted",
) -> pd.DataFrame:
    metric_column = f"{metric}_{aggregation}"

    if metric_column not in summary.columns:
        raise ValueError(f"Metric column not found: {metric_column}")

    wide = summary.pivot_table(
        index="case_id",
        columns="heuristic",
        values=metric_column,
        aggfunc="first",
        observed=False,
    ).reset_index()

    for heuristic in HEURISTIC_ORDER:
        if heuristic not in wide.columns:
            wide[heuristic] = float("nan")

    return wide[["case_id", *HEURISTIC_ORDER]]


def write_markdown_report(
    *,
    out_dir: Path,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metric: str,
    baseline: str,
) -> Path:
    report_path = out_dir / "comparison_report.md"

    metric_column = f"{metric}_weighted"
    pct_column = f"{metric_column}_pct_vs_{baseline}"

    lines: list[str] = []

    lines.append("# Congestion heuristic comparison")
    lines.append("")
    lines.append(f"Main metric: `{metric_column}`")
    lines.append(f"Baseline: `{baseline}`")
    lines.append("")
    lines.append("## Summary by case")
    lines.append("")

    for case_id, case_df in summary.groupby("case_id"):
        lines.append(f"### {case_id}")
        lines.append("")

        compact_columns = [
            "heuristic",
            "groups",
            "total_n_records",
            metric_column,
        ]

        compact_columns = [
            column
            for column in compact_columns
            if column in case_df.columns
        ]

        compact = case_df[compact_columns].copy()

        if not compact.empty:
            lines.append(compact.to_markdown(index=False))
            lines.append("")

        case_comp = comparison[comparison["case_id"] == case_id]

        if pct_column in case_comp.columns:
            deltas = case_comp[
                [
                    "heuristic",
                    metric_column,
                    pct_column,
                ]
            ].copy()

            lines.append(f"Change in `{metric}` vs `{baseline}`:")
            lines.append("")
            lines.append(deltas.to_markdown(index=False))
            lines.append("")

    lines.append("## Best heuristic by metric")
    lines.append("")

    if best_by_metric.empty:
        lines.append("_No best-metric data available._")
    else:
        lines.append(best_by_metric.to_markdown(index=False))

    lines.append("")

    report_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return report_path


def write_outputs(
    *,
    out_dir: Path,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metric: str,
    baseline: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    combined.to_csv(
        out_dir / "combined_group_metrics.csv",
        index=False,
    )

    summary.to_csv(
        out_dir / "summary_by_case_heuristic.csv",
        index=False,
    )

    comparison.to_csv(
        out_dir / "comparison_vs_baseline.csv",
        index=False,
    )

    best_by_metric.to_csv(
        out_dir / "best_by_metric.csv",
        index=False,
    )

    for aggregation in ["weighted", "mean", "median"]:
        metric_column = f"{metric}_{aggregation}"

        if metric_column not in summary.columns:
            continue

        wide = build_wide_table(
            summary,
            metric=metric,
            aggregation=aggregation,
        )

        wide.to_csv(
            out_dir / f"wide_{metric}_{aggregation}.csv",
            index=False,
        )

    report_path = write_markdown_report(
        out_dir=out_dir,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        metric=metric,
        baseline=baseline,
    )

    print(f"Report written to: {report_path}")


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
        print()
        print("Incomplete cases:")

        for case_id, missing in incomplete_cases:
            print(f"  - {case_id}: missing {', '.join(missing)}")

    if require_all_heuristics:
        return summary[summary["case_id"].isin(complete_cases)].copy()

    return summary


def main() -> int:
    args = parse_args()

    runs_dir = args.runs_dir.resolve()
    out_dir = args.out_dir or (runs_dir / DEFAULT_OUTPUT_DIR_NAME)

    combined = load_all_group_metrics(
        runs_dir=runs_dir,
        heuristics=args.heuristics,
        cases=args.cases,
    )

    summary = build_summary(combined)

    summary = validate_completeness(
        summary=summary,
        selected_heuristics=args.heuristics,
        require_all_heuristics=args.require_all_heuristics,
    )

    comparison = build_comparison_vs_baseline(
        summary,
        baseline=args.baseline,
    )

    best_by_metric = build_best_by_metric(summary)

    write_outputs(
        out_dir=out_dir,
        combined=combined,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        metric=args.metric,
        baseline=args.baseline,
    )

    print()
    print("Comparison files written to:")
    print(f"  {out_dir}")
    print()
    print("Main files:")
    print("  - combined_group_metrics.csv")
    print("  - summary_by_case_heuristic.csv")
    print("  - comparison_vs_baseline.csv")
    print("  - best_by_metric.csv")
    print("  - comparison_report.md")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())