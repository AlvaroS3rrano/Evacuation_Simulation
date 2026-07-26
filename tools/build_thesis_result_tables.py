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
  - mean_speed_by_scenario      -> estadísticas de velocidad por agente (m/s):
                                   media, mediana, desviación típica, mínimo,
                                   p10, p90 y máximo, por escenario, con
                                   variación % respecto a la base para la
                                   media y el mínimo. Requiere haber ejecutado
                                   antes ``tools/compute_mean_speed_by_scenario.py``
                                   (lee las trayectorias .sqlite crudas, algo
                                   que este script deliberadamente no hace);
                                   si no se ha ejecutado, esta tabla se omite.

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
    "avg_speed": "Vmed",
    "median_speed": "Vmediana",
    "std_speed": "Vstd",
    "min_speed": "Vmin",
    "p10_speed": "Vp10",
    "p90_speed": "Vp90",
    "max_speed": "Vmax",
}

# The two metrics the user asked for explicitly: mean evacuation time and
# mean density exposure.
DIFF_METRICS = ["avg_evac_time", "avg_density_exposure"]

# Per-agent walking speed statistics (m/s), computed by
# compute_mean_speed_by_scenario.py directly from the raw trajectory .sqlite
# files (not derivable from the already-aggregated comparison_metrics.csv).
# avg_speed is the headline metric; the rest cover the full operating range
# (median/std/min/p10/p90/max), e.g. min/p10 show how slow agents get during
# the worst congestion moments.
SPEED_METRIC = "avg_speed"
SPEED_METRICS = [
    "avg_speed",
    "median_speed",
    "min_speed",
    "p10_speed",
    "p90_speed",
    "max_speed",
    "std_speed",
]
# Metrics that also get a %-vs-baseline column in the mean-speed table: the
# headline average, and the worst-case (min) speed, since "how much worse
# does congestion get" is the more thesis-relevant question for the tail.
SPEED_DELTA_METRICS = ["avg_speed", "min_speed"]


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


def load_mean_speed_csvs(run_root: Path) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Load the mean-speed scenario CSVs, or None if the (optional) prerequisite
    step hasn't been run yet.

    Unlike load_scenario_strategy_csvs, this does not raise: the mean-speed
    table/figure are additive extras, so their absence shouldn't block the
    other four tables from being generated.
    """
    strategy_dir = run_root / "comparison" / "scenario_strategy"
    summary_path = strategy_dir / "scenario_mean_speed_summary.csv"
    delta_path = strategy_dir / "scenario_mean_speed_delta_vs_baseline.csv"

    if not summary_path.exists() or not delta_path.exists():
        return None

    return pd.read_csv(summary_path), pd.read_csv(delta_path)


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


def _build_metric_table(
    summary: pd.DataFrame,
    delta: pd.DataFrame,
    baseline: str,
    metrics: list[str],
    *,
    delta_metrics: list[str] | None = None,
) -> pd.DataFrame:
    """One row per (scenario, heuristic), with a `{label}_mean` column per
    metric and a `{label}_delta_pct` column for the metrics in `delta_metrics`
    (all of `metrics` by default). Shared by build_diff_time_density (Tevac/D)
    and build_mean_speed_by_scenario (speed statistics) since both need the
    same "mean + %-vs-baseline per metric" shape.
    """
    if delta_metrics is None:
        delta_metrics = metrics

    rows = []
    scenarios = sorted(summary["scenario"].unique())
    for scenario in scenarios:
        for heuristic in HEURISTIC_ORDER:
            row = {"scenario": scenario, "heuristic": heuristic}
            for metric in metrics:
                mean_val = summary.loc[
                    (summary["scenario"] == scenario)
                    & (summary["heuristic"] == heuristic)
                    & (summary["metric"] == metric),
                    "mean",
                ]
                row[f"{label(metric)}_mean"] = (
                    float(mean_val.iloc[0]) if not mean_val.empty else float("nan")
                )

                if metric not in delta_metrics:
                    continue

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


def build_diff_time_density(
    summary: pd.DataFrame, delta: pd.DataFrame, baseline: str
) -> pd.DataFrame:
    """Core requested table: mean Tevac/D per strategy, plus % change vs
    baseline, per scenario."""
    return _build_metric_table(summary, delta, baseline, DIFF_METRICS)


def build_mean_speed_by_scenario(
    speed_summary: pd.DataFrame, speed_delta: pd.DataFrame, baseline: str
) -> pd.DataFrame:
    """Per-agent walking speed statistics (m/s) per strategy and scenario —
    mean, median, min, p10, p90, max, std — plus % change vs. the baseline
    for the headline mean and the worst-case (min) speed. Same shape as
    build_diff_time_density, for the metrics produced by
    compute_mean_speed_by_scenario.py.
    """
    return _build_metric_table(
        speed_summary,
        speed_delta,
        baseline,
        SPEED_METRICS,
        delta_metrics=SPEED_DELTA_METRICS,
    )


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
    mean_speed: pd.DataFrame | None,
    baseline: str,
    decimals: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    mean_results.to_csv(output_dir / "mean_results_by_scenario.csv", index=False)
    diff_time_density.to_csv(output_dir / "diff_time_density_vs_baseline.csv", index=False)
    best_strategy.to_csv(output_dir / "best_strategy_by_scenario.csv", index=False)
    robustness.to_csv(output_dir / "robustness_cv.csv", index=False)

    if mean_speed is not None:
        mean_speed.to_csv(output_dir / "mean_speed_by_scenario.csv", index=False)

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

    lines.append("## 5. Estadísticas de velocidad de los agentes\n")
    if mean_speed is not None:
        lines.append(
            "Estadísticas de velocidad por agente (m/s), calculadas directamente "
            "sobre las trayectorias registradas por JuPedSim (no derivadas de "
            "`avg_path_cost`): `Vmed` (media), `Vmediana`, `Vstd` (desviación "
            "típica), `Vmin`, `Vp10`, `Vp90` y `Vmax`. `Vmin`/`Vp10` reflejan "
            "cómo de lentos se mueven los agentes en los momentos de mayor "
            "congestión. Se incluye variación porcentual respecto a la "
            f"estrategia base (`{baseline}`) para `Vmed` y `Vmin`.\n"
        )
        lines.append(markdown_table(mean_speed, decimals) + "\n")
    else:
        lines.append(
            "_No disponible: ejecuta `python tools/compute_mean_speed_by_scenario.py "
            "--run-root <run-root>` antes de este script para generar esta tabla._\n"
        )

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

    speed_csvs = load_mean_speed_csvs(run_root)
    if speed_csvs is None:
        print(
            "[mean-speed] not found under comparison/scenario_strategy/ - skipping "
            "table 5. Run `python tools/compute_mean_speed_by_scenario.py "
            f"--run-root {run_root}` first to include it."
        )
        mean_speed = None
    else:
        speed_summary, speed_delta = speed_csvs
        mean_speed = build_mean_speed_by_scenario(speed_summary, speed_delta, args.baseline)

    report_path = write_report(
        output_dir,
        mean_results=mean_results,
        diff_time_density=diff_time_density,
        best_strategy=best_strategy,
        robustness=robustness,
        mean_speed=mean_speed,
        baseline=args.baseline,
        decimals=args.decimals,
    )

    print(f"Wrote tables to: {output_dir}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
