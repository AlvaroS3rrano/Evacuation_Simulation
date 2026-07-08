"""Build TFM-style comparison figures from an already-processed congestion run.

Consumes the same scenario-level CSVs as ``build_thesis_result_tables.py``
(produced by ``compare_congestion_by_scenario.py``, step 6 of
``tools/COMANDOS_REALIZACION_TFM.md``) and renders four figures aimed at the
thesis discussion (Chapter 7):

  1. dispersion_outliers  -> per-configuration dots for Tevac and D, grouped
                              by strategy and scenario, with the most extreme
                              case per group labelled by its case suffix.
  2. mean_comparison       -> grouped bars of mean Tevac / D per strategy and
                              scenario, with +/-1 std error bars.
  3. delta_vs_baseline     -> percentage change of Tevac / D for h1/h2/h3
                              relative to the baseline (none), per scenario.
  4. tradeoff_scatter      -> Tevac vs. D scatter per scenario, individual
                              configurations plus per-strategy mean markers,
                              illustrating the speed/congestion compromise.

Each figure is written as both PDF (vector, for \\includegraphics in the
thesis) and PNG (quick preview).

Usage:
    python tools/build_thesis_result_figures.py \\
        --run-root runs/congestion_heuristics_efficient_high
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_thesis_result_tables import (
    DIFF_METRICS,
    HEURISTIC_ORDER,
    METRIC_LABELS,
    PROJECT_ROOT,
    label,
    load_scenario_case_values,
    load_scenario_strategy_csvs,
    scenario_label,
)

# Categorical palette (dataviz skill, references/palette.md): fixed order,
# validated for CVD separation. "none" is deliberately a neutral gray since
# it is the reference baseline, not a peer category being compared.
COLORS = {
    "none": "#6b6b66",
    "h1": "#2a78d6",
    "h2": "#1baf7a",
    "h3": "#eb6834",
}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render comparison figures (dispersion/outliers, mean bars, "
            "delta vs baseline, time-vs-density trade-off) from the "
            "scenario_strategy outputs of compare_congestion_by_scenario.py."
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
        help="Output folder. Default: <run-root>/comparison/thesis_tables/figures",
    )
    parser.add_argument(
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic used for delta/trade-off reference.",
    )
    parser.add_argument("--dpi", type=int, default=200, help="PNG raster resolution.")
    return parser.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": "sans-serif",
            "font.size": 9.5,
            "text.color": INK_PRIMARY,
            "axes.edgecolor": INK_MUTED,
            "axes.labelcolor": INK_PRIMARY,
            "axes.titlecolor": INK_PRIMARY,
            "xtick.color": INK_SECONDARY,
            "ytick.color": INK_SECONDARY,
            "axes.grid": True,
            "grid.color": GRIDLINE,
            "grid.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )


def short_case_label(case_id: str) -> str:
    if case_id.startswith("base_"):
        return "base"
    m = re.search(r"_(\d+)$", case_id)
    return m.group(1) if m else case_id


def save(fig: plt.Figure, out_dir: Path, name: str, dpi: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        path = out_dir / f"{name}.{ext}"
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def fig_dispersion_outliers(case_df: pd.DataFrame, out_dir: Path, dpi: int) -> list[Path]:
    scenarios = [s for s in case_df["scenario"].unique()]
    scenarios = sorted(scenarios)
    heuristics = [h for h in HEURISTIC_ORDER if h in case_df["heuristic"].unique()]

    fig, axes = plt.subplots(
        len(DIFF_METRICS),
        len(scenarios),
        figsize=(4.2 * len(scenarios), 3.4 * len(DIFF_METRICS)),
        squeeze=False,
    )

    rng = np.random.default_rng(0)

    for row, metric in enumerate(DIFF_METRICS):
        for col, scenario in enumerate(scenarios):
            ax = axes[row][col]
            sub = case_df[case_df["scenario"] == scenario]

            for x, heuristic in enumerate(heuristics):
                values = sub.loc[sub["heuristic"] == heuristic, metric].dropna()
                case_ids = sub.loc[sub["heuristic"] == heuristic, "case_id"]
                if values.empty:
                    continue

                jitter = rng.uniform(-0.12, 0.12, size=len(values))
                ax.scatter(
                    np.full(len(values), x) + jitter,
                    values,
                    s=32,
                    color=COLORS[heuristic],
                    alpha=0.55,
                    edgecolors="none",
                    zorder=2,
                )

                mean = values.mean()
                std = values.std(ddof=1) if len(values) > 1 else 0.0
                ax.errorbar(
                    [x],
                    [mean],
                    yerr=[std],
                    fmt="D",
                    color=INK_PRIMARY,
                    markerfacecolor=COLORS[heuristic],
                    markeredgecolor=INK_PRIMARY,
                    markersize=6,
                    linewidth=1.1,
                    capsize=3,
                    zorder=3,
                )

                # Label the most extreme configuration in the group so it
                # can be traced back to a specific case_id.
                idx_extreme = values.idxmax() if (values.max() - mean) >= (mean - values.min()) else values.idxmin()
                extreme_value = values.loc[idx_extreme]
                extreme_case = short_case_label(case_ids.loc[idx_extreme])
                ax.annotate(
                    extreme_case,
                    (x + 0.16, extreme_value),
                    fontsize=7,
                    color=INK_SECONDARY,
                    va="center",
                )

            ax.set_xticks(range(len(heuristics)))
            ax.set_xticklabels(heuristics)
            ax.set_xlim(-0.5, len(heuristics) - 0.5)
            if col == 0:
                ax.set_ylabel(label(metric))
            if row == 0:
                ax.set_title(scenario_label(scenario), fontsize=10)

    fig.suptitle(
        "Dispersión por configuración y valores atípicos "
        "(rombo = media ± desviación típica; etiqueta = configuración más extrema)",
        fontsize=10.5,
        y=1.02,
    )
    fig.tight_layout()
    return save(fig, out_dir, "dispersion_outliers", dpi)


def fig_mean_comparison(summary: pd.DataFrame, out_dir: Path, dpi: int) -> list[Path]:
    scenarios = sorted(summary["scenario"].unique())
    heuristics = [h for h in HEURISTIC_ORDER if h in summary["heuristic"].unique()]

    fig, axes = plt.subplots(1, len(DIFF_METRICS), figsize=(6.2 * len(DIFF_METRICS), 4.2))

    n_heuristics = len(heuristics)
    group_width = 0.8
    bar_width = group_width / n_heuristics

    for panel, metric in enumerate(DIFF_METRICS):
        ax = axes[panel]
        for h_idx, heuristic in enumerate(heuristics):
            means, stds = [], []
            for scenario in scenarios:
                row = summary[
                    (summary["scenario"] == scenario)
                    & (summary["heuristic"] == heuristic)
                    & (summary["metric"] == metric)
                ]
                means.append(float(row["mean"].iloc[0]) if not row.empty else np.nan)
                stds.append(float(row["std"].iloc[0]) if not row.empty else 0.0)

            offsets = (h_idx - (n_heuristics - 1) / 2) * bar_width
            positions = np.arange(len(scenarios)) + offsets
            ax.bar(
                positions,
                means,
                width=bar_width * 0.92,
                yerr=stds,
                capsize=3,
                color=COLORS[heuristic],
                edgecolor=INK_PRIMARY,
                linewidth=0.5,
                label=heuristic,
            )

        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels([scenario_label(s) for s in scenarios], rotation=10)
        ax.set_ylabel(label(metric))
        ax.set_title(label(metric), fontsize=10.5)
        ax.margins(y=0.12)

    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[h]) for h in heuristics]
    fig.legend(
        handles,
        heuristics,
        loc="lower center",
        ncol=len(heuristics),
        bbox_to_anchor=(0.5, -0.06),
        title="Estrategia",
    )
    fig.suptitle(
        "Tiempo medio de evacuación y exposición media a densidad por estrategia y escenario",
        fontsize=11,
        y=1.03,
    )
    fig.tight_layout()
    return save(fig, out_dir, "mean_comparison", dpi)


def fig_delta_vs_baseline(delta: pd.DataFrame, out_dir: Path, baseline: str, dpi: int) -> list[Path]:
    scenarios = sorted(delta["scenario"].unique())
    heuristics = [h for h in HEURISTIC_ORDER if h != baseline and h in delta["heuristic"].unique()]

    fig, axes = plt.subplots(1, len(DIFF_METRICS), figsize=(6.2 * len(DIFF_METRICS), 4.2))

    n_heuristics = len(heuristics)
    group_width = 0.7
    bar_width = group_width / n_heuristics

    for panel, metric in enumerate(DIFF_METRICS):
        ax = axes[panel]
        for h_idx, heuristic in enumerate(heuristics):
            values = []
            for scenario in scenarios:
                row = delta[
                    (delta["scenario"] == scenario)
                    & (delta["heuristic"] == heuristic)
                    & (delta["metric"] == metric)
                ]
                values.append(float(row["delta_pct_mean"].iloc[0]) if not row.empty else np.nan)

            offsets = (h_idx - (n_heuristics - 1) / 2) * bar_width
            positions = np.arange(len(scenarios)) + offsets
            bars = ax.bar(
                positions,
                values,
                width=bar_width * 0.9,
                color=COLORS[heuristic],
                edgecolor=INK_PRIMARY,
                linewidth=0.5,
                label=heuristic,
            )
            for rect, value in zip(bars, values):
                if np.isnan(value):
                    continue
                va = "bottom" if value >= 0 else "top"
                offset = 1.5 if value >= 0 else -1.5
                ax.annotate(
                    f"{value:+.0f}%",
                    (rect.get_x() + rect.get_width() / 2, value + offset),
                    ha="center",
                    va=va,
                    fontsize=7,
                    color=INK_SECONDARY,
                )

        ax.axhline(0, color=INK_MUTED, linewidth=1)
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels([scenario_label(s) for s in scenarios], rotation=10)
        ax.set_ylabel(f"Δ {label(metric)} vs. {baseline} (%)")
        ax.set_title(label(metric), fontsize=10.5)
        ax.margins(y=0.18)

    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[h]) for h in heuristics]
    fig.legend(
        handles,
        heuristics,
        loc="lower center",
        ncol=len(heuristics),
        bbox_to_anchor=(0.5, -0.06),
        title="Estrategia",
    )
    fig.suptitle(
        f"Variación porcentual respecto a la estrategia base ({baseline})",
        fontsize=11,
        y=1.03,
    )
    fig.tight_layout()
    return save(fig, out_dir, "delta_vs_baseline", dpi)


def fig_tradeoff_scatter(case_df: pd.DataFrame, summary: pd.DataFrame, out_dir: Path, dpi: int) -> list[Path]:
    scenarios = sorted(case_df["scenario"].unique())
    heuristics = [h for h in HEURISTIC_ORDER if h in case_df["heuristic"].unique()]

    fig, axes = plt.subplots(1, len(scenarios), figsize=(5.2 * len(scenarios), 4.6), squeeze=False)
    axes = axes[0]

    time_metric, density_metric = "avg_evac_time", "avg_density_exposure"

    # Fixed per-heuristic label quadrant so labels for strategies whose means
    # land close together (frequent for h1/h2/h3) don't stack on top of each
    # other: none top-left, h1 top-right, h2 bottom-right, h3 bottom-left.
    label_offsets = {
        "none": ((-8, 9), "right"),
        "h1": ((8, 9), "left"),
        "h2": ((8, -13), "left"),
        "h3": ((-8, -13), "right"),
    }

    for col, scenario in enumerate(scenarios):
        ax = axes[col]
        sub = case_df[case_df["scenario"] == scenario]

        for heuristic in heuristics:
            group = sub[sub["heuristic"] == heuristic]
            if group.empty:
                continue

            ax.scatter(
                group[time_metric],
                group[density_metric],
                s=26,
                color=COLORS[heuristic],
                alpha=0.4,
                edgecolors="none",
                zorder=2,
            )

            mean_x = group[time_metric].mean()
            mean_y = group[density_metric].mean()
            ax.scatter(
                [mean_x],
                [mean_y],
                s=90,
                color=COLORS[heuristic],
                edgecolors=INK_PRIMARY,
                linewidths=1.1,
                zorder=3,
            )
            xytext, ha = label_offsets.get(heuristic, ((6, 6), "left"))
            ax.annotate(
                heuristic,
                (mean_x, mean_y),
                textcoords="offset points",
                xytext=xytext,
                ha=ha,
                fontsize=8.5,
                color=INK_PRIMARY,
                fontweight="bold",
            )

        ax.set_xlabel(label(time_metric))
        if col == 0:
            ax.set_ylabel(label(density_metric))
        ax.set_title(scenario_label(scenario), fontsize=10.5)

    fig.suptitle(
        "Compromiso entre tiempo de evacuación y exposición a densidad "
        "(puntos pequeños = configuraciones individuales; puntos grandes = media por estrategia)",
        fontsize=10.5,
        y=1.04,
    )
    fig.tight_layout()
    return save(fig, out_dir, "tradeoff_scatter", dpi)


def main() -> int:
    args = parse_args()
    run_root = _resolve(args.run_root)
    output_dir = (
        _resolve(args.output_dir)
        if args.output_dir
        else run_root / "comparison" / "thesis_tables" / "figures"
    )

    apply_style()

    summary, delta = load_scenario_strategy_csvs(run_root)
    case_values = load_scenario_case_values(run_root)

    written: list[Path] = []
    written += fig_dispersion_outliers(case_values, output_dir, args.dpi)
    written += fig_mean_comparison(summary, output_dir, args.dpi)
    written += fig_delta_vs_baseline(delta, output_dir, args.baseline, args.dpi)
    written += fig_tradeoff_scatter(case_values, summary, output_dir, args.dpi)

    print(f"Wrote {len(written)} files to: {output_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
