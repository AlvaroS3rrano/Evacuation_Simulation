"""Build TFM-style result tables from an already-processed congestion run.

This script does not re-read the simulation databases. It consumes the
scenario-level CSVs already produced by ``compare_congestion_by_scenario.py``
(step 6 of ``tools/COMANDOS_REALIZACION_TFM.md``):

    <run-root>/comparison/scenario_strategy/scenario_metric_summary.csv
    <run-root>/comparison/scenario_strategy/scenario_delta_vs_baseline.csv

and reshapes them into the tables used in Chapter 7 of the TFM:

  - mean_results_by_scenario   -> Tablas 7.1 / 7.2 / 7.3 (resultados medios)
  - diff_time_density          -> tabla principal solicitada: diferencias de
                                   Tevac y D (media + variación %) respecto a
                                   la estrategia base, por escenario
  - best_strategy_by_scenario  -> Tabla 7.4 (síntesis: mejor tiempo / mejor
                                   congestión por escenario)
  - robustness_cv              -> Tabla 7.5 (coeficiente de variación y % de
                                   configuraciones en que cada heurística
                                   reduce la densidad frente a la base)

Run this after step 6 of the pipeline, e.g.:

    python tools/build_thesis_result_tables.py \\
        --run-root runs/congestion_heuristics_efficient_high
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

# Spanish scenario names matching the thesis wording, keyed by the scenario
# codes produced by compare_congestion_by_scenario.py's scenario_from_case_id().
SCENARIO_LABELS = {
    "two_corridors": "Pasillos paralelos",
    "short_vs_wide": "Ruta corta vs. ruta amplia",
    "two_exits": "Dos salidas",
}

METRIC_LABELS = {
    "avg_evac_time": "Tevac",
    "median_evac_time": "Tmedian_evac",
    "p90_evac_time": "T90_evac",
    "max_evac_time": "Tmax_evac",
    "avg_density_exposure": "D",
    "p90_density_exposure": "D90",
    "peak_area_density": "D_peak",
    "high_density_agent_ratio": "Rhigh",
    "congestion_density_score": "CongScore",
    "avg_path_cost": "Cpath",
}

# The two metrics the user asked for explicitly: mean evacuation time and
# mean density exposure.
DIFF_METRICS = ["avg_evac_time", "avg_density_exposure"]


def label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build TFM-style comparison tables (mean time/density, deltas "
            "vs baseline, best strategy per scenario, CV/robustness) from "
            "the scenario_strategy outputs of compare_congestion_by_scenario.py."
        )
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/congestion_heuristics_efficient_high"),
        help="Root folder used for the run (same value passed to "
        "compare_congestion_by_scenario.py --run-root).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output folder. Default: <run-root>/comparison/thesis_tables",
    )
    parser.add_argument(
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic used for delta/robustness tables.",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        default=2,
        help="Decimal places used when rendering Markdown tables.",
    )
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_scenario_strategy_csvs(run_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy_dir = run_root / "comparison" / "scenario_strategy"
    summary_path = strategy_dir / "scenario_metric_summary.csv"
    delta_path = strategy_dir / "scenario_delta_vs_baseline.csv"

    missing = [p for p in (summary_path, delta_path) if not p.exists()]
    if missing:
        missing_list = "\n  ".join(str(p) for p in missing)
        raise FileNotFoundError(
            "Missing scenario_strategy CSV(s):\n  "
            f"{missing_list}\n\n"
            "Run compare_congestion_by_scenario.py first, e.g.:\n"
            f"  python tools/compare_congestion_by_scenario.py --run-root {run_root}"
        )

    summary = pd.read_csv(summary_path)
    delta = pd.read_csv(delta_path)
    return summary, delta


def load_scenario_case_values(run_root: Path) -> pd.DataFrame:
    """Per-(case, heuristic) metric values — one row per evaluated
    configuration. This is the finest-grained data available without
    re-reading the simulation databases, and is what outlier/dispersion
    charts need (scenario_metric_summary.csv only has aggregates)."""
    path = run_root / "comparison" / "scenario_strategy" / "scenario_case_metric_values.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}\n\n"
            "Run compare_congestion_by_scenario.py first, e.g.:\n"
            f"  python tools/compare_congestion_by_scenario.py --run-root {run_root}"
        )
    return pd.read_csv(path)


def scenario_label(scenario: str) -> str:
    return SCENARIO_LABELS.get(scenario, scenario)


def order_categorical(df: pd.DataFrame, column: str, order: list[str]) -> pd.DataFrame:
    present = [v for v in order if v in df[column].unique()]
    df = df.copy()
    df[column] = pd.Categorical(df[column], categories=present, ordered=True)
    return df.sort_values([column]).reset_index(drop=True)


def build_mean_results_by_scenario(summary: pd.DataFrame) -> pd.DataFrame:
    """One row per (scenario, heuristic), one column per metric mean.

    Mirrors TFM tables 7.1/7.2/7.3 (mean results per scenario over the
    evaluated configurations), but combined across all scenarios.
    """
    pivot = summary.pivot_table(
        index=["scenario", "heuristic"], columns="metric", values="mean"
    ).reset_index()
    pivot.columns.name = None

    metric_cols = [c for c in pivot.columns if c not in ("scenario", "heuristic")]
    pivot = pivot.rename(columns={c: label(c) for c in metric_cols})

    pivot = order_categorical(pivot, "heuristic", HEURISTIC_ORDER)
    pivot = pivot.sort_values(["scenario", "heuristic"]).reset_index(drop=True)
    return pivot


def build_diff_time_density(
    summary: pd.DataFrame, delta: pd.DataFrame, baseline: str
) -> pd.DataFrame:
    """Core requested table: mean Tevac/D per strategy, plus % change vs
    baseline, per scenario."""
    rows = []
    scenarios = sorted(summary["scenario"].unique())
    for scenario in scenarios:
        for heuristic in HEURISTIC_ORDER:
            row = {"scenario": scenario, "heuristic": heuristic}
            for metric in DIFF_METRICS:
                mean_val = summary.loc[
                    (summary["scenario"] == scenario)
                    & (summary["heuristic"] == heuristic)
                    & (summary["metric"] == metric),
                    "mean",
                ]
                row[f"{label(metric)}_mean"] = (
                    float(mean_val.iloc[0]) if not mean_val.empty else float("nan")
                )

                if heuristic == baseline:
                    row[f"{label(metric)}_delta_pct"] = 0.0
                else:
                    delta_val = delta.loc[
                        (delta["scenario"] == scenario)
                        & (delta["heuristic"] == heuristic)
                        & (delta["metric"] == metric),
                        "delta_pct_mean",
                    ]
                    row[f"{label(metric)}_delta_pct"] = (
                        float(delta_val.iloc[0]) if not delta_val.empty else float("nan")
                    )
            rows.append(row)

    out = pd.DataFrame(rows)
    out = order_categorical(out, "heuristic", HEURISTIC_ORDER)
    out = out.sort_values(["scenario", "heuristic"]).reset_index(drop=True)
    return out


def build_best_strategy_by_scenario(summary: pd.DataFrame) -> pd.DataFrame:
    """Mirrors TFM Table 7.4: which heuristic gets the best (lowest) value
    per key metric, per scenario. All PRIMARY_METRICS here are
    lower-is-better (see comparison.lower_is_better in default_metrics.yaml).
    """
    candidate_metrics = [
        m
        for m in ("avg_evac_time", "avg_density_exposure", "high_density_agent_ratio")
        if m in summary["metric"].unique()
    ]

    rows = []
    for scenario, group in summary.groupby("scenario"):
        row = {"scenario": scenario}
        for metric in candidate_metrics:
            sub = group[group["metric"] == metric]
            if sub.empty:
                continue
            best = sub.loc[sub["mean"].idxmin()]
            row[f"mejor_{label(metric)}_heuristica"] = best["heuristic"]
            row[f"mejor_{label(metric)}_valor"] = float(best["mean"])
        rows.append(row)

    out = pd.DataFrame(rows).sort_values("scenario").reset_index(drop=True)
    return out


def build_robustness_cv(
    summary: pd.DataFrame, delta: pd.DataFrame, baseline: str
) -> pd.DataFrame:
    """Mirrors TFM Table 7.5: CV% of Tevac and D across configurations per
    (scenario, heuristic), plus % of configurations where each heuristic
    reduces density relative to the baseline (win_rate_vs_baseline_pct for
    avg_density_exposure, which is lower-is-better).
    """
    rows = []
    scenarios = sorted(summary["scenario"].unique())
    for scenario in scenarios:
        for heuristic in HEURISTIC_ORDER:
            row = {"scenario": scenario, "heuristic": heuristic}
            for metric in DIFF_METRICS:
                cv_val = summary.loc[
                    (summary["scenario"] == scenario)
                    & (summary["heuristic"] == heuristic)
                    & (summary["metric"] == metric),
                    "cv_pct",
                ]
                row[f"CV_{label(metric)}_pct"] = (
                    float(cv_val.iloc[0]) if not cv_val.empty else float("nan")
                )

            if heuristic == baseline:
                row["mejora_densidad_pct_configs"] = float("nan")
            else:
                win_val = delta.loc[
                    (delta["scenario"] == scenario)
                    & (delta["heuristic"] == heuristic)
                    & (delta["metric"] == "avg_density_exposure"),
                    "win_rate_vs_baseline_pct",
                ]
                row["mejora_densidad_pct_configs"] = (
                    float(win_val.iloc[0]) if not win_val.empty else float("nan")
                )
            rows.append(row)

    out = pd.DataFrame(rows)
    out = order_categorical(out, "heuristic", HEURISTIC_ORDER)
    out = out.sort_values(["scenario", "heuristic"]).reset_index(drop=True)
    return out


def markdown_table(df: pd.DataFrame, decimals: int) -> str:
    if df.empty:
        return "_No data available._"
    rounded = df.copy()
    for col in rounded.select_dtypes(include="number").columns:
        rounded[col] = rounded[col].round(decimals)
    return rounded.to_markdown(index=False)


def write_report(
    output_dir: Path,
    *,
    mean_results: pd.DataFrame,
    diff_time_density: pd.DataFrame,
    best_strategy: pd.DataFrame,
    robustness: pd.DataFrame,
    baseline: str,
    decimals: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    mean_results.to_csv(output_dir / "mean_results_by_scenario.csv", index=False)
    diff_time_density.to_csv(output_dir / "diff_time_density_vs_baseline.csv", index=False)
    best_strategy.to_csv(output_dir / "best_strategy_by_scenario.csv", index=False)
    robustness.to_csv(output_dir / "robustness_cv.csv", index=False)

    lines: list[str] = []
    lines.append("# Tablas de resultados (generado automáticamente)\n")
    lines.append(f"Estrategia base: `{baseline}`\n")

    lines.append("## 1. Diferencias de tiempo medio de evacuación y densidad media\n")
    lines.append(
        "Media de `Tevac` y `D` por estrategia, y variación porcentual respecto a "
        f"la estrategia base (`{baseline}`), por escenario.\n"
    )
    lines.append(markdown_table(diff_time_density, decimals) + "\n")

    lines.append("## 2. Resultados medios por escenario\n")
    lines.append(
        "Media de cada métrica por estrategia y escenario, sobre las "
        "configuraciones evaluadas.\n"
    )
    for scenario in sorted(mean_results["scenario"].unique()):
        lines.append(f"### {scenario_label(scenario)} (`{scenario}`)\n")
        sub = mean_results[mean_results["scenario"] == scenario].drop(columns=["scenario"])
        lines.append(markdown_table(sub, decimals) + "\n")

    lines.append("## 3. Síntesis: mejor estrategia por escenario\n")
    lines.append(
        "Heurística con el valor medio más bajo (mejor) para cada métrica clave, "
        "por escenario.\n"
    )
    lines.append(markdown_table(best_strategy, decimals) + "\n")

    lines.append("## 4. Variabilidad y robustez\n")
    lines.append(
        "Coeficiente de variación (CV %) de `Tevac` y `D` entre configuraciones "
        "de un mismo escenario, y porcentaje de configuraciones en las que cada "
        f"heurística reduce la densidad respecto a `{baseline}`.\n"
    )
    lines.append(markdown_table(robustness, decimals) + "\n")

    report_path = output_dir / "thesis_tables_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    run_root = _resolve(args.run_root)
    output_dir = _resolve(args.output_dir) if args.output_dir else run_root / "comparison" / "thesis_tables"

    summary, delta = load_scenario_strategy_csvs(run_root)

    mean_results = build_mean_results_by_scenario(summary)
    diff_time_density = build_diff_time_density(summary, delta, args.baseline)
    best_strategy = build_best_strategy_by_scenario(summary)
    robustness = build_robustness_cv(summary, delta, args.baseline)

    report_path = write_report(
        output_dir,
        mean_results=mean_results,
        diff_time_density=diff_time_density,
        best_strategy=best_strategy,
        robustness=robustness,
        baseline=args.baseline,
        decimals=args.decimals,
    )

    print(f"Wrote tables to: {output_dir}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
