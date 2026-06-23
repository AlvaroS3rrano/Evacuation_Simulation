from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

PRIMARY_METRICS = [
    "avg_evac_time",
    "p90_evac_time",
    "max_evac_time",
    "avg_density_exposure",
    "high_density_agent_ratio",
]

COMPOSITE_WEIGHTS = {
    "avg_evac_time": 0.35,
    "p90_evac_time": 0.25,
    "max_evac_time": 0.10,
    "avg_density_exposure": 0.15,
    "high_density_agent_ratio": 0.15,
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
        help="Root folder containing heuristic result folders.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output folder. Default: <run-root>/comparison/scenario_strategy",
    )

    parser.add_argument(
        "--exclude-base",
        action="store_true",
        help="Exclude base_* cases from scenario-level statistics.",
    )

    parser.add_argument(
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic for percentage comparisons.",
    )

    return parser.parse_args()


def scenario_from_case_id(case_id: str) -> str:
    if case_id.startswith("base_"):
        return case_id.removeprefix("base_")

    if case_id.startswith("random_"):
        body = case_id.removeprefix("random_")
        return re.sub(r"_\d+$", "", body)

    return case_id


def is_base_case(case_id: str) -> bool:
    return case_id.startswith("base_")


def discover_metric_files(run_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

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


def find_column(df: pd.DataFrame, metric: str) -> str | None:
    for candidate in [f"{metric}_weighted", metric]:
        if candidate in df.columns:
            return candidate

    return None


def weighted_average(values: pd.Series, weights: pd.Series | None) -> float:
    values = pd.to_numeric(values, errors="coerce")

    if weights is None:
        return float(values.mean())

    weights = pd.to_numeric(weights, errors="coerce")

    valid = values.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        return float(values.mean())

    return float(np.average(values[valid], weights=weights[valid]))


def read_case_metric(row: dict[str, object]) -> dict[str, object] | None:
    csv_path = Path(row["metrics_path"])

    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return None

    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return None

    if df.empty:
        return None

    weights = None

    for weight_col in ["n_records", "total_n_records", "records", "agents"]:
        if weight_col in df.columns:
            weights = df[weight_col]
            break

    result: dict[str, object] = {
        "case_id": row["case_id"],
        "scenario": row["scenario"],
        "heuristic": row["heuristic"],
        "is_base_case": is_base_case(str(row["case_id"])),
        "metrics_path": str(csv_path),
    }

    for metric in PRIMARY_METRICS:
        col = find_column(df, metric)

        if col is None:
            result[metric] = np.nan
        else:
            result[metric] = weighted_average(df[col], weights)

    return result


def build_case_metrics(
    metric_files: list[dict[str, object]],
    *,
    exclude_base: bool,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for metric_file in metric_files:
        if exclude_base and is_base_case(str(metric_file["case_id"])):
            continue

        row = read_case_metric(metric_file)

        if row is not None:
            rows.append(row)

    if not rows:
        raise RuntimeError("No readable comparison_metrics.csv files found.")

    return pd.DataFrame(rows)


def to_long(case_metrics: pd.DataFrame) -> pd.DataFrame:
    long_df = case_metrics.melt(
        id_vars=[
            "case_id",
            "scenario",
            "heuristic",
            "is_base_case",
            "metrics_path",
        ],
        value_vars=PRIMARY_METRICS,
        var_name="metric",
        value_name="value",
    )

    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    return long_df.dropna(subset=["value"])


def build_metric_summary(long_df: pd.DataFrame) -> pd.DataFrame:
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
        )
    )

    summary["std"] = summary["std"].fillna(0.0)
    summary["var"] = summary["var"].fillna(0.0)

    summary["cv_pct"] = np.where(
        summary["mean"].abs() > 0,
        100.0 * summary["std"] / summary["mean"].abs(),
        np.nan,
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

    merged["delta_abs_vs_baseline"] = merged["value"] - merged["baseline_value"]

    merged["delta_pct_vs_baseline"] = np.where(
        merged["baseline_value"].abs() > 0,
        100.0 * merged["delta_abs_vs_baseline"] / merged["baseline_value"],
        np.nan,
    )

    merged["wins_vs_baseline"] = merged["delta_abs_vs_baseline"] < 0

    summary = (
        merged
        .groupby(["scenario", "heuristic", "metric"], as_index=False)
        .agg(
            n_cases=("case_id", "nunique"),
            delta_pct_mean=("delta_pct_vs_baseline", "mean"),
            delta_pct_std=("delta_pct_vs_baseline", "std"),
            wins_vs_baseline=("wins_vs_baseline", "sum"),
        )
    )

    summary["delta_pct_std"] = summary["delta_pct_std"].fillna(0.0)

    summary["win_rate_vs_baseline_pct"] = np.where(
        summary["n_cases"] > 0,
        100.0 * summary["wins_vs_baseline"] / summary["n_cases"],
        np.nan,
    )

    return summary


def build_composite_scores(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []

    for (_, _, metric), group in long_df.groupby(["scenario", "case_id", "metric"]):
        group = group.copy()

        min_value = group["value"].min()
        max_value = group["value"].max()

        if math.isclose(float(max_value), float(min_value)):
            group["normalized_score"] = 0.0
        else:
            group["normalized_score"] = (
                (group["value"] - min_value) / (max_value - min_value)
            )

        group["weight"] = group["metric"].map(COMPOSITE_WEIGHTS)
        rows.append(group)

    normalized = pd.concat(rows, ignore_index=True)

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

    composite_summary = (
        case_scores
        .groupby(["scenario", "heuristic"], as_index=False)
        .agg(
            n_cases=("case_id", "nunique"),
            composite_mean=("composite_score", "mean"),
            composite_std=("composite_score", "std"),
            composite_var=("composite_score", "var"),
        )
    )

    composite_summary["composite_std"] = composite_summary["composite_std"].fillna(0.0)
    composite_summary["composite_var"] = composite_summary["composite_var"].fillna(0.0)

    composite_summary["rank"] = (
        composite_summary
        .sort_values(["scenario", "composite_mean"])
        .groupby("scenario")
        .cumcount()
        + 1
    )

    return case_scores, composite_summary


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No data available._"

    display = df.copy()

    for col in display.columns:
        if pd.api.types.is_numeric_dtype(display[col]):
            display[col] = display[col].map(
                lambda x: "" if pd.isna(x) else round(float(x), 4)
            )

    return display.to_markdown(index=False)


def write_report(
    *,
    output_path: Path,
    metric_summary: pd.DataFrame,
    delta_summary: pd.DataFrame,
    composite_summary: pd.DataFrame,
    baseline: str,
    exclude_base: bool,
) -> None:
    lines: list[str] = []

    lines.append("# Scenario-level congestion heuristic comparison")
    lines.append("")
    lines.append("Each case belonging to a scenario is treated as one observation.")
    lines.append("")
    lines.append(f"Baseline heuristic: `{baseline}`")
    lines.append(f"Base cases excluded: `{exclude_base}`")
    lines.append("")
    lines.append("Primary metrics:")
    lines.append("")
    for metric in PRIMARY_METRICS:
        lines.append(f"- `{metric}`")
    lines.append("")

    lines.append("## Composite ranking by scenario")
    lines.append("")
    lines.append(
        markdown_table(
            composite_summary
            .sort_values(["scenario", "rank"])
            [[
                "scenario",
                "rank",
                "heuristic",
                "n_cases",
                "composite_mean",
                "composite_std",
                "composite_var",
            ]]
        )
    )
    lines.append("")

    for scenario in sorted(metric_summary["scenario"].unique()):
        lines.append(f"## Scenario: `{scenario}`")
        lines.append("")

        for metric in PRIMARY_METRICS:
            metric_table = metric_summary[
                (metric_summary["scenario"] == scenario)
                & (metric_summary["metric"] == metric)
            ].copy()

            metric_delta = delta_summary[
                (delta_summary["scenario"] == scenario)
                & (delta_summary["metric"] == metric)
            ][
                [
                    "heuristic",
                    "delta_pct_mean",
                    "delta_pct_std",
                    "win_rate_vs_baseline_pct",
                ]
            ]

            table = metric_table.merge(
                metric_delta,
                on="heuristic",
                how="left",
            )

            table["heuristic"] = pd.Categorical(
                table["heuristic"],
                categories=HEURISTIC_ORDER,
                ordered=True,
            )

            table = table.sort_values("heuristic")

            lines.append(f"### Metric: `{metric}`")
            lines.append("")
            lines.append(
                markdown_table(
                    table[
                        [
                            "heuristic",
                            "n_cases",
                            "mean",
                            "std",
                            "cv_pct",
                            "delta_pct_mean",
                            "delta_pct_std",
                            "win_rate_vs_baseline_pct",
                        ]
                    ]
                )
            )
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
        raise RuntimeError(f"No comparison_metrics.csv files found under {run_root}")

    case_metrics = build_case_metrics(
        metric_files,
        exclude_base=args.exclude_base,
    )

    long_df = to_long(case_metrics)
    metric_summary = build_metric_summary(long_df)
    delta_summary = build_delta_vs_baseline(long_df, baseline=args.baseline)
    case_scores, composite_summary = build_composite_scores(long_df)

    case_metrics.to_csv(output_dir / "scenario_case_metric_values.csv", index=False)
    long_df.to_csv(output_dir / "scenario_case_metric_values_long.csv", index=False)
    metric_summary.to_csv(output_dir / "scenario_metric_summary.csv", index=False)
    delta_summary.to_csv(output_dir / "scenario_delta_vs_baseline.csv", index=False)
    case_scores.to_csv(output_dir / "scenario_case_composite_scores.csv", index=False)
    composite_summary.to_csv(output_dir / "scenario_composite_summary.csv", index=False)

    report_path = output_dir / "scenario_strategy_report.md"

    write_report(
        output_path=report_path,
        metric_summary=metric_summary,
        delta_summary=delta_summary,
        composite_summary=composite_summary,
        baseline=args.baseline,
        exclude_base=args.exclude_base,
    )

    print()
    print("=" * 80)
    print("Scenario-level comparison generated")
    print("=" * 80)
    print(f"Output dir: {output_dir}")
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
