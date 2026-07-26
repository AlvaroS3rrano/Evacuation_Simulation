"""Compute per-agent walking speed statistics per case, aggregated by scenario.

For each case/heuristic, computes mean, median, std, min, p10, p90, and max
of every individual agent/frame speed sample (m/s) — not just the mean — so
the resulting table/figure can show the full operating range (e.g. how slow
agents get during the worst congestion moments), not only the average.

Unlike ``build_thesis_result_tables.py`` / ``build_thesis_result_figures.py``,
this script DOES re-read the raw per-agent trajectory sqlite files
(``artifacts/db/<env>_mode_<n>.sqlite``, the same files used by
``congestion_analysis/congestion_gif.py``), because walking speed cannot be
derived from the already-aggregated ``comparison_metrics.csv`` files that
``compare_congestion_by_scenario.py`` consumes: that pipeline's
``avg_path_cost`` is a time-averaged *remaining* route distance, not a total
distance travelled, so ``avg_path_cost / avg_evac_time`` would not be a
physically meaningful speed.

Run this once per run-root, after ``compare_congestion_by_scenario.py``, so
that ``build_thesis_result_tables.py`` / ``build_thesis_result_figures.py``
can then consume its (small, already-aggregated) output the same way they
consume the other ``scenario_strategy`` CSVs:

    python tools/compute_mean_speed_by_scenario.py \\
        --run-root runs/congestion_heuristics_efficient_high
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pedpy
import pandas as pd

from compare_congestion_by_scenario import (
    HEURISTIC_ORDER,
    build_delta_vs_baseline,
    build_metric_summary,
    scenario_from_case_id,
)
from congestion_analysis.congestion_gif import load_pedpy_trajectory
from congestion_analysis.visualization import choose_trajectory_db

# Primary (headline) metric, plus the full set of per-case speed statistics
# computed from the individual agent/frame speed samples. All in m/s.
SPEED_METRIC = "avg_speed"
SPEED_METRICS = [
    "avg_speed",
    "median_speed",
    "std_speed",
    "min_speed",
    "p10_speed",
    "p90_speed",
    "max_speed",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute mean per-agent walking speed (m/s) per case from the raw "
            "trajectory sqlite files, aggregated by scenario in the same shape "
            "as compare_congestion_by_scenario.py's outputs."
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
        "--baseline",
        default="none",
        choices=HEURISTIC_ORDER,
        help="Baseline heuristic for percentage comparisons.",
    )
    parser.add_argument(
        "--exclude-base",
        action="store_true",
        help="Exclude base_* cases from scenario-level statistics.",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=5,
        help="frame_step passed to pedpy.compute_individual_speed.",
    )
    return parser.parse_args()


def discover_case_dirs(run_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    for heuristic_dir in sorted(run_root.iterdir()):
        if not heuristic_dir.is_dir() or heuristic_dir.name not in HEURISTIC_ORDER:
            continue

        heuristic = heuristic_dir.name

        for case_dir in sorted(heuristic_dir.iterdir()):
            if not case_dir.is_dir():
                continue

            case_id = case_dir.name
            rows.append(
                {
                    "case_id": case_id,
                    "scenario": scenario_from_case_id(case_id),
                    "heuristic": heuristic,
                    "case_dir": case_dir,
                }
            )

    return rows


def compute_case_speed_stats(case_dir: Path, frame_step: int) -> dict[str, float] | None:
    """Summary statistics (m/s) of every individual agent/frame speed sample
    recorded for this case, covering both central tendency (mean, median) and
    spread (std, min, p10, p90, max) — the min/p10 end in particular is what
    shows how slow agents get during the worst congestion moments."""
    db_path = choose_trajectory_db(case_dir)
    if db_path is None:
        return None

    traj = load_pedpy_trajectory(db_path)
    if traj is None or traj.data.empty:
        return None

    speed_df = pedpy.compute_individual_speed(
        traj_data=traj,
        frame_step=frame_step,
        speed_calculation=pedpy.SpeedCalculation.BORDER_SINGLE_SIDED,
    )
    if speed_df.empty:
        return None

    speeds = speed_df[pedpy.SPEED_COL]
    return {
        "avg_speed": float(speeds.mean()),
        "median_speed": float(speeds.median()),
        "std_speed": float(speeds.std(ddof=1)) if len(speeds) > 1 else 0.0,
        "min_speed": float(speeds.min()),
        "p10_speed": float(speeds.quantile(0.10)),
        "p90_speed": float(speeds.quantile(0.90)),
        "max_speed": float(speeds.max()),
    }


def build_case_speed_values(
    cases: list[dict[str, object]],
    *,
    exclude_base: bool,
    frame_step: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for case in cases:
        case_id = str(case["case_id"])

        if exclude_base and case_id.startswith("base_"):
            continue

        try:
            stats = compute_case_speed_stats(Path(str(case["case_dir"])), frame_step)
        except Exception as exc:
            print(f"[mean-speed] WARN case={case_id} heuristic={case['heuristic']} error={exc}")
            continue

        if stats is None:
            print(
                f"[mean-speed] SKIP case={case_id} heuristic={case['heuristic']} "
                "reason=no trajectory data"
            )
            continue

        for metric in SPEED_METRICS:
            rows.append(
                {
                    "case_id": case_id,
                    "scenario": case["scenario"],
                    "heuristic": case["heuristic"],
                    "is_base_case": case_id.startswith("base_"),
                    "metric": metric,
                    "value": stats[metric],
                }
            )
        print(
            f"[mean-speed] case={case_id} heuristic={case['heuristic']} "
            f"avg={stats['avg_speed']:.3f} median={stats['median_speed']:.3f} "
            f"std={stats['std_speed']:.3f} min={stats['min_speed']:.3f} "
            f"p10={stats['p10_speed']:.3f} p90={stats['p90_speed']:.3f} "
            f"max={stats['max_speed']:.3f} m/s"
        )

    if not rows:
        raise RuntimeError(
            "No case produced a mean speed value. Check that the per-agent "
            "trajectory .sqlite files exist under artifacts/db/ for these cases."
        )

    return pd.DataFrame(rows)


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

    cases = discover_case_dirs(run_root)
    if not cases:
        raise RuntimeError(f"No heuristic/case folders found under {run_root}")

    long_df = build_case_speed_values(
        cases,
        exclude_base=args.exclude_base,
        frame_step=args.frame_step,
    )

    metric_summary = build_metric_summary(long_df)
    delta_summary = build_delta_vs_baseline(long_df, baseline=args.baseline)

    long_df.to_csv(output_dir / "scenario_mean_speed_case_values.csv", index=False)
    metric_summary.to_csv(output_dir / "scenario_mean_speed_summary.csv", index=False)
    delta_summary.to_csv(output_dir / "scenario_mean_speed_delta_vs_baseline.csv", index=False)

    print()
    print(f"Wrote mean-speed CSVs to: {output_dir}")
    print("  scenario_mean_speed_case_values.csv")
    print("  scenario_mean_speed_summary.csv")
    print("  scenario_mean_speed_delta_vs_baseline.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
