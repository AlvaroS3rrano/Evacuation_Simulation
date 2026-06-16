from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
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

AGGREGATIONS = ["mean", "median", "weighted"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare congestion heuristic results across cases. "
            "The report shows mean, median and n_records-weighted metrics so h3 "
            "is not judged only by a potentially biased weighted value."
        )
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
        help="Output directory for comparison files. Default: <runs-dir>/comparison",
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
        "--aggregation",
        default="mean",
        choices=AGGREGATIONS,
        help=(
            "Aggregation used as the headline metric. "
            "Use mean/median for a fairer per-group comparison; weighted uses n_records."
        ),
    )

    parser.add_argument(
        "--require-all-heuristics",
        action="store_true",
        help="Skip cases that do not have results for all selected heuristics.",
    )

    parser.add_argument(
        "--group-mismatch-warn-pct",
        type=float,
        default=20.0,
        help=(
            "Warn when the number of groups for a heuristic differs from the baseline "
            "by more than this percentage."
        ),
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


def _file_timestamp(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def discover_metric_files(
    *,
    runs_dir: Path,
    heuristics: list[str],
) -> list[dict[str, Any]]:
    metric_files: list[dict[str, Any]] = []

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
                    {
                        "heuristic": heuristic,
                        "case_id": case_dir.name,
                        "case_dir": case_dir,
                        "metrics_path": metrics_path,
                        "modified_at": _file_timestamp(metrics_path),
                    }
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
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_files = discover_metric_files(
        runs_dir=runs_dir,
        heuristics=heuristics,
    )

    frames: list[pd.DataFrame] = []
    inputs: list[dict[str, Any]] = []

    requested_cases = set(cases or [])

    for item in metric_files:
        heuristic = item["heuristic"]
        case_id = item["case_id"]
        metrics_path = item["metrics_path"]

        if requested_cases and case_id not in requested_cases:
            continue

        df = safe_read_csv(metrics_path)

        row_count = 0 if df is None else len(df)
        inputs.append(
            {
                "case_id": case_id,
                "heuristic": heuristic,
                "metrics_path": str(metrics_path),
                "modified_at": item.get("modified_at"),
                "rows": row_count,
                "loaded": df is not None and not df.empty,
            }
        )

        if df is None or df.empty:
            continue

        df = df.copy()
        df.insert(0, "heuristic", heuristic)
        df.insert(1, "case_id", case_id)
        df.insert(2, "metrics_path", str(metrics_path))

        if "case_name" in df.columns:
            df["mode"] = df["case_name"].astype(str).str.extract(r"_mode_(\d+)$")[0]
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

    return combined, pd.DataFrame(inputs)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    clean = pd.DataFrame({"value": values, "weight": weights}).dropna()
    clean = clean[clean["weight"] > 0]

    if clean.empty:
        return float("nan")

    return float((clean["value"] * clean["weight"]).sum() / clean["weight"].sum())


def aggregate_case_heuristic(group: pd.DataFrame) -> pd.Series:
    if "n_records" in group.columns:
        weights = group["n_records"]
    else:
        weights = pd.Series([1.0] * len(group), index=group.index)

    result: dict[str, Any] = {
        "groups": int(len(group)),
        "total_n_records": float(group["n_records"].sum())
        if "n_records" in group.columns
        else float(len(group)),
        "metrics_path": "; ".join(sorted(set(group["metrics_path"].astype(str)))),
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


def percentage_delta(value: float, baseline: float) -> float:
    if baseline is None:
        return float("nan")

    if pd.isna(value) or pd.isna(baseline):
        return float("nan")

    if math.isclose(float(baseline), 0.0):
        return float("nan")

    return float(((value - baseline) / baseline) * 100.0)


def build_comparison_vs_baseline(
    summary: pd.DataFrame,
    *,
    baseline: str,
) -> pd.DataFrame:
    metric_fields = [
        column
        for column in summary.columns
        if column.endswith("_weighted")
        or column.endswith("_mean")
        or column.endswith("_median")
    ]

    baseline_df = summary[summary["heuristic"] == baseline][
        ["case_id", "groups", "total_n_records", *metric_fields]
    ].copy()

    rename_map = {
        "groups": "groups_baseline",
        "total_n_records": "total_n_records_baseline",
        **{column: f"{column}_baseline" for column in metric_fields},
    }

    baseline_df = baseline_df.rename(columns=rename_map)

    comparison = summary.merge(
        baseline_df,
        on="case_id",
        how="left",
    )

    comparison["groups_delta_vs_baseline"] = (
        comparison["groups"] - comparison["groups_baseline"]
    )
    comparison["groups_pct_vs_baseline"] = comparison.apply(
        lambda row: percentage_delta(row["groups"], row["groups_baseline"]),
        axis=1,
    )

    comparison["total_n_records_delta_vs_baseline"] = (
        comparison["total_n_records"] - comparison["total_n_records_baseline"]
    )
    comparison["total_n_records_pct_vs_baseline"] = comparison.apply(
        lambda row: percentage_delta(row["total_n_records"], row["total_n_records_baseline"]),
        axis=1,
    )

    for metric_field in metric_fields:
        baseline_column = f"{metric_field}_baseline"
        delta_column = f"{metric_field}_delta_vs_{baseline}"
        pct_column = f"{metric_field}_pct_vs_{baseline}"

        comparison[delta_column] = comparison[metric_field] - comparison[baseline_column]
        comparison[pct_column] = comparison.apply(
            lambda row: percentage_delta(row[metric_field], row[baseline_column]),
            axis=1,
        )

    return comparison


def build_best_by_metric(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for case_id, case_df in summary.groupby("case_id", observed=False):
        for metric in METRIC_COLUMNS:
            for aggregation in AGGREGATIONS:
                column = f"{metric}_{aggregation}"

                if column not in case_df.columns:
                    continue

                valid = case_df.dropna(subset=[column])

                if valid.empty:
                    continue

                ascending = LOWER_IS_BETTER.get(metric, True)
                best_row = valid.sort_values(column, ascending=ascending).iloc[0]

                rows.append(
                    {
                        "case_id": case_id,
                        "metric": metric,
                        "aggregation": aggregation,
                        "best_heuristic": best_row["heuristic"],
                        "best_value": best_row[column],
                    }
                )

    return pd.DataFrame(rows)


def build_wide_table(
    summary: pd.DataFrame,
    *,
    metric: str,
    aggregation: str,
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


def validate_completeness(
    *,
    summary: pd.DataFrame,
    selected_heuristics: list[str],
    require_all_heuristics: bool,
) -> tuple[pd.DataFrame, list[str]]:
    expected = set(selected_heuristics)

    complete_cases: list[str] = []
    warnings: list[str] = []

    for case_id, case_df in summary.groupby("case_id", observed=False):
        present = set(case_df["heuristic"].astype(str))
        missing = sorted(expected - present)

        if missing:
            warnings.append(f"{case_id}: missing {', '.join(missing)}")
        else:
            complete_cases.append(case_id)

    if require_all_heuristics:
        summary = summary[summary["case_id"].isin(complete_cases)].copy()

    return summary, warnings


def build_sanity_checks(
    *,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    inputs: pd.DataFrame,
    baseline: str,
    group_mismatch_warn_pct: float,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for case_id, case_df in summary.groupby("case_id", observed=False):
        heuristics_present = set(case_df["heuristic"].astype(str))
        missing = sorted(set(HEURISTIC_ORDER) - heuristics_present)

        checks.append(
            {
                "case_id": case_id,
                "check": "all_standard_heuristics_present",
                "status": "PASS" if not missing else "WARN",
                "details": "-" if not missing else f"Missing: {', '.join(missing)}",
            }
        )

        h3_rows = case_df[case_df["heuristic"].astype(str) == "h3"]
        checks.append(
            {
                "case_id": case_id,
                "check": "h3_metrics_loaded",
                "status": "PASS" if not h3_rows.empty else "FAIL",
                "details": "-" if not h3_rows.empty else "No h3 row found in summary.",
            }
        )

        baseline_rows = case_df[case_df["heuristic"].astype(str) == baseline]
        if baseline_rows.empty:
            checks.append(
                {
                    "case_id": case_id,
                    "check": "baseline_available",
                    "status": "FAIL",
                    "details": f"Baseline {baseline!r} not found.",
                }
            )
            continue

        base_groups = float(baseline_rows.iloc[0]["groups"])

        for _, row in case_df.iterrows():
            heuristic = str(row["heuristic"])
            pct = percentage_delta(float(row["groups"]), base_groups)

            if heuristic == baseline or pd.isna(pct):
                continue

            status = "WARN" if abs(pct) > group_mismatch_warn_pct else "PASS"
            checks.append(
                {
                    "case_id": case_id,
                    "check": f"group_count_vs_{baseline}:{heuristic}",
                    "status": status,
                    "details": (
                        f"{heuristic} groups={row['groups']}, {baseline} groups={base_groups}, "
                        f"delta={pct:.2f}%"
                    ),
                }
            )

    if not inputs.empty:
        failed_inputs = inputs[~inputs["loaded"]]
        checks.append(
            {
                "case_id": "*",
                "check": "all_discovered_metric_files_loaded",
                "status": "PASS" if failed_inputs.empty else "WARN",
                "details": "-" if failed_inputs.empty else f"{len(failed_inputs)} input files were not loaded.",
            }
        )

    return checks


def _format_number(value: Any, decimals: int = 4) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "-"

    if pd.isna(value):
        return "-"

    return f"{value:.{decimals}f}"


def write_markdown_report(
    *,
    out_dir: Path,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    inputs: pd.DataFrame,
    sanity_checks: list[dict[str, Any]],
    metric: str,
    aggregation: str,
    baseline: str,
) -> Path:
    report_path = out_dir / "comparison_report.md"

    metric_column = f"{metric}_{aggregation}"
    pct_column = f"{metric_column}_pct_vs_{baseline}"

    lines: list[str] = []

    lines.append("# Congestion heuristic comparison")
    lines.append("")
    lines.append(f"Headline metric: `{metric_column}`")
    lines.append(f"Baseline: `{baseline}`")
    lines.append("")
    lines.append("> Note: `weighted` uses `n_records` as weights. If `n_records` grows with simulation duration, ")
    lines.append("> it can overweight slower trajectories. Use `mean` or `median` for a cleaner per-group comparison.")
    lines.append("")
    lines.append("## Summary by case")
    lines.append("")

    for case_id, case_df in summary.groupby("case_id", observed=False):
        lines.append(f"### {case_id}")
        lines.append("")

        compact_columns = [
            "heuristic",
            "groups",
            "total_n_records",
            f"{metric}_mean",
            f"{metric}_median",
            f"{metric}_weighted",
        ]
        compact_columns = [column for column in compact_columns if column in case_df.columns]
        compact = case_df[compact_columns].copy()

        if not compact.empty:
            lines.append(compact.to_markdown(index=False))
            lines.append("")

        case_comp = comparison[comparison["case_id"] == case_id]

        delta_columns = [
            "heuristic",
            metric_column,
            pct_column,
            "groups",
            "groups_pct_vs_baseline",
            "total_n_records",
            "total_n_records_pct_vs_baseline",
        ]
        delta_columns = [column for column in delta_columns if column in case_comp.columns]

        if delta_columns:
            deltas = case_comp[delta_columns].copy()
            lines.append(f"Change in `{metric_column}` vs `{baseline}`:")
            lines.append("")
            lines.append(deltas.to_markdown(index=False))
            lines.append("")

    lines.append("## h3 sanity view")
    lines.append("")

    h3_rows = summary[summary["heuristic"].astype(str) == "h3"].copy()
    if h3_rows.empty:
        lines.append("_No h3 rows were found._")
    else:
        h3_cols = [
            "case_id",
            "groups",
            "total_n_records",
            f"{metric}_mean",
            f"{metric}_median",
            f"{metric}_weighted",
            "metrics_path",
        ]
        h3_cols = [col for col in h3_cols if col in h3_rows.columns]
        lines.append(h3_rows[h3_cols].to_markdown(index=False))

    lines.append("")
    lines.append("## Sanity checks")
    lines.append("")

    if sanity_checks:
        checks_df = pd.DataFrame(sanity_checks)
        lines.append(checks_df.to_markdown(index=False))
    else:
        lines.append("_No sanity checks were generated._")

    lines.append("")
    lines.append("## Input metric files")
    lines.append("")

    if inputs.empty:
        lines.append("_No input file metadata available._")
    else:
        lines.append(inputs.to_markdown(index=False))

    lines.append("")
    lines.append("## Best heuristic by metric")
    lines.append("")

    if best_by_metric.empty:
        lines.append("_No best-metric data available._")
    else:
        best_filtered = best_by_metric[
            (best_by_metric["metric"] == metric)
            | (best_by_metric["aggregation"] == aggregation)
        ].copy()
        if best_filtered.empty:
            best_filtered = best_by_metric
        lines.append(best_filtered.to_markdown(index=False))

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
    inputs: pd.DataFrame,
    sanity_checks: list[dict[str, Any]],
    metric: str,
    aggregation: str,
    baseline: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    combined.to_csv(out_dir / "combined_group_metrics.csv", index=False)
    summary.to_csv(out_dir / "summary_by_case_heuristic.csv", index=False)
    comparison.to_csv(out_dir / "comparison_vs_baseline.csv", index=False)
    best_by_metric.to_csv(out_dir / "best_by_metric.csv", index=False)
    inputs.to_csv(out_dir / "input_metric_files.csv", index=False)
    pd.DataFrame(sanity_checks).to_csv(out_dir / "sanity_checks.csv", index=False)

    for metric_name in METRIC_COLUMNS:
        for aggregation_name in AGGREGATIONS:
            metric_column = f"{metric_name}_{aggregation_name}"
            if metric_column not in summary.columns:
                continue

            wide = build_wide_table(
                summary,
                metric=metric_name,
                aggregation=aggregation_name,
            )
            wide.to_csv(out_dir / f"wide_{metric_name}_{aggregation_name}.csv", index=False)

    report_path = write_markdown_report(
        out_dir=out_dir,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        inputs=inputs,
        sanity_checks=sanity_checks,
        metric=metric,
        aggregation=aggregation,
        baseline=baseline,
    )

    manifest = {
        "runs_dir": str(out_dir.parent),
        "output_dir": str(out_dir),
        "metric": metric,
        "aggregation": aggregation,
        "baseline": baseline,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": [
            "combined_group_metrics.csv",
            "summary_by_case_heuristic.csv",
            "comparison_vs_baseline.csv",
            "best_by_metric.csv",
            "input_metric_files.csv",
            "sanity_checks.csv",
            "comparison_report.md",
        ],
    }
    (out_dir / "comparison_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("Comparison finished.")
    print(f"Headline metric: {metric}_{aggregation}")
    print(f"Report: {report_path}")
    print()


def print_terminal_summary(
    *,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    metric: str,
    aggregation: str,
    baseline: str,
) -> None:
    metric_column = f"{metric}_{aggregation}"
    pct_column = f"{metric_column}_pct_vs_{baseline}"

    print("Compact comparison:")
    for case_id, case_df in comparison.groupby("case_id", observed=False):
        print(f"\n{case_id}")
        for heuristic in HEURISTIC_ORDER:
            rows = case_df[case_df["heuristic"].astype(str) == heuristic]
            if rows.empty:
                continue
            row = rows.iloc[0]
            value = _format_number(row.get(metric_column), 3)
            pct = _format_number(row.get(pct_column), 2)
            groups = row.get("groups", "-")
            records = row.get("total_n_records", "-")
            suffix = "" if heuristic == baseline else f" ({pct}% vs {baseline})"
            print(
                f"  - {heuristic:<4} {metric_column}={value}{suffix} "
                f"| groups={groups} records={records}"
            )


def main() -> int:
    args = parse_args()

    runs_dir = args.runs_dir.resolve()
    out_dir = args.out_dir or (runs_dir / DEFAULT_OUTPUT_DIR_NAME)

    combined, inputs = load_all_group_metrics(
        runs_dir=runs_dir,
        heuristics=args.heuristics,
        cases=args.cases,
    )

    summary = build_summary(combined)

    summary, completeness_warnings = validate_completeness(
        summary=summary,
        selected_heuristics=args.heuristics,
        require_all_heuristics=args.require_all_heuristics,
    )

    if completeness_warnings:
        print()
        print("Completeness warnings:")
        for warning in completeness_warnings:
            print(f"  - {warning}")

    comparison = build_comparison_vs_baseline(summary, baseline=args.baseline)
    best_by_metric = build_best_by_metric(summary)

    sanity_checks = build_sanity_checks(
        summary=summary,
        comparison=comparison,
        inputs=inputs,
        baseline=args.baseline,
        group_mismatch_warn_pct=args.group_mismatch_warn_pct,
    )

    write_outputs(
        out_dir=out_dir,
        combined=combined,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        inputs=inputs,
        sanity_checks=sanity_checks,
        metric=args.metric,
        aggregation=args.aggregation,
        baseline=args.baseline,
    )

    print_terminal_summary(
        summary=summary,
        comparison=comparison,
        metric=args.metric,
        aggregation=args.aggregation,
        baseline=args.baseline,
    )

    warn_count = sum(1 for check in sanity_checks if check["status"] == "WARN")
    fail_count = sum(1 for check in sanity_checks if check["status"] == "FAIL")

    print()
    print(f"Sanity checks: {fail_count} FAIL, {warn_count} WARN")

    if fail_count:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
