from __future__ import annotations

import argparse
from pathlib import Path

from congestion_analysis.comparison import (
    HEURISTIC_ORDER,
    build_best_by_metric,
    build_comparison_vs_baseline,
    build_summary,
    configured_main_metrics,
    load_all_metrics,
    load_metrics_config,
    lower_is_better_map,
    validate_completeness,
)
from congestion_analysis.report import write_outputs
from congestion_analysis.visualization import generate_visual_comparison_pdfs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = PROJECT_ROOT / "runs" / "congestion_heuristics_efficient_high"
DEFAULT_METRICS_CONFIG = PROJECT_ROOT / "configs" / "metrics" / "default_metrics.yaml"
DEFAULT_OUTPUT_DIR_NAME = "comparison"


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
    parser.add_argument(
        "--simulation-config",
        type=Path,
        default=None,
        help=(
            "Scenario configuration YAML used to resolve environments for visual PDFs. "
            "If omitted, the script searches under configs/."
        ),
    )
    parser.add_argument(
        "--density-frames",
        nargs="*",
        type=int,
        default=None,
        help=(
            "Explicit density frames rendered in the visual PDFs. "
            "If omitted, frames are generated automatically from --density-frame-step."
        ),
    )
    parser.add_argument(
        "--density-frame-step",
        type=int,
        default=500,
        help=(
            "Automatic step used for density pages when --density-frames is not provided. "
            "Example: 500 -> 0, 500, 1000, ... plus the terminal frame if needed."
        ),
    )
    parser.add_argument(
        "--no-terminal-density-frame",
        action="store_true",
        help="Do not append the final common terminal frame when using automatic density frames.",
    )
    parser.add_argument(
        "--skip-visual-pdfs",
        action="store_true",
        help="Do not generate trajectory/density comparison PDFs.",
    )
    parser.add_argument(
        "--visual-subdir",
        default="visual_snapshots",
        help="Subdirectory inside comparison/ where visual PDFs are stored.",
    )
    parser.add_argument(
        "--trajectory-frame-stride",
        type=int,
        default=10,
        help="Frame stride used only when a trajectory image is not found and a fallback plot must be rebuilt.",
    )
    parser.add_argument(
        "--trajectory-max-agents",
        type=int,
        default=300,
        help="Maximum number of agents plotted in fallback trajectory panels. Use <=0 for all.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    runs_dir = args.runs_dir.resolve()
    out_dir = args.out_dir or runs_dir / DEFAULT_OUTPUT_DIR_NAME

    metrics_config = load_metrics_config(
        args.metrics_config,
        project_root=PROJECT_ROOT,
    )
    metrics = configured_main_metrics(metrics_config)
    main_metric = args.metric or metrics[0]

    if main_metric not in metrics:
        metrics = [main_metric, *metrics]

    combined = load_all_metrics(
        runs_dir=runs_dir,
        heuristics=args.heuristics,
        cases=args.cases,
    )

    summary = build_summary(combined, metrics)

    summary = validate_completeness(
        summary=summary,
        selected_heuristics=args.heuristics,
        require_all_heuristics=args.require_all_heuristics,
    )

    comparison = build_comparison_vs_baseline(
        summary,
        baseline=args.baseline,
    )

    best_by_metric = build_best_by_metric(
        summary,
        metrics=metrics,
        lower_is_better=lower_is_better_map(metrics_config),
    )

    visual_pdf_paths = []

    if not args.skip_visual_pdfs:
        visual_pdf_paths = generate_visual_comparison_pdfs(
            summary=summary,
            project_root=PROJECT_ROOT,
            comparison_dir=out_dir,
            simulation_config=args.simulation_config,
            heuristics=args.heuristics,
            density_frames=args.density_frames,
            density_frame_step=args.density_frame_step,
            include_terminal_density_frame=not args.no_terminal_density_frame,
            visual_subdir=args.visual_subdir,
            trajectory_frame_stride=args.trajectory_frame_stride,
            trajectory_max_agents=(
                None
                if args.trajectory_max_agents <= 0
                else args.trajectory_max_agents
            ),
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
        visual_pdf_paths=visual_pdf_paths,
    )

    print()
    print("Comparison finished.")
    print(f"Output directory: {out_dir}")
    print(f"Main metric: {main_metric}")

    if visual_pdf_paths:
        print("Visual PDFs:")
        for pdf_path in visual_pdf_paths:
            print(f"  - {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())