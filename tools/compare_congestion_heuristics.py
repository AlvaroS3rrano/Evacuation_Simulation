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
from congestion_analysis.congestion_gif import generate_congestion_gifs
from congestion_analysis.report import write_outputs
from congestion_analysis.visualization import (
    generate_trajectory_time_evolution_images,
    generate_visual_comparison_pdfs,
)


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
    parser.add_argument(
        "--skip-trajectory-time-evolution",
        action="store_true",
        help="Do not generate the per-case trajectory image colored by frame bin.",
    )
    parser.add_argument(
        "--trajectory-time-bin-size",
        type=int,
        default=500,
        help=(
            "Frame width of each color bin in the trajectory time-evolution image "
            "(e.g. 500 -> frames 0-500 one color, 500-1000 the next, ...). Independent "
            "of --density-frame-step."
        ),
    )
    parser.add_argument(
        "--trajectory-time-subdir",
        default="trajectory_time_evolution",
        help="Subdirectory inside comparison/ where trajectory time-evolution images are stored.",
    )
    parser.add_argument(
        "--skip-congestion-gifs",
        action="store_true",
        help="Do not generate per-case Voronoi-density congestion GIFs.",
    )
    parser.add_argument(
        "--congestion-gif-subdir",
        default="congestion_gifs",
        help="Subdirectory inside comparison/ where congestion GIFs (and highlight snapshots) are stored.",
    )
    parser.add_argument(
        "--gif-max-frames",
        type=int,
        default=60,
        help="Target number of frames sampled for the congestion GIF when --gif-frame-step is not set.",
    )
    parser.add_argument(
        "--gif-frame-step",
        type=int,
        default=None,
        help="Explicit stride (in raw simulation frame units) between congestion GIF frames.",
    )
    parser.add_argument(
        "--gif-fps",
        type=int,
        default=8,
        help="Playback speed (frames per second) of the saved congestion GIF.",
    )
    parser.add_argument(
        "--voronoi-cutoff-radius",
        type=float,
        default=None,
        help="Optional max radius (meters) for individual Voronoi cells. Omit for no cutoff.",
    )
    parser.add_argument(
        "--gif-cmap",
        default="YlGn",
        help="Matplotlib colormap used to color Voronoi cells by density.",
    )
    parser.add_argument(
        "--congestion-highlight-frames",
        nargs="*",
        type=int,
        default=None,
        help=(
            "Extra frames to save as standalone congestion snapshot PNGs (one per case, "
            "all heuristics), in addition to the GIF."
        ),
    )
    parser.add_argument(
        "--time-unit",
        choices=["frame", "seconds"],
        default="frame",
        help=(
            "Unit used to label frames in titles, colorbars, and highlight-frame "
            "filenames across visual PDFs, trajectory time-evolution images, and "
            "congestion GIFs. Does not change which frames are selected/sampled — "
            "those are still given in raw frame numbers via the other flags. "
            "Falls back to frame with a console warning if fps can't be read "
            "from a case's trajectory database."
        ),
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
    trajectory_time_evolution_paths = []
    congestion_gif_paths = []
    congestion_highlight_paths = []

    trajectory_max_agents = None if args.trajectory_max_agents <= 0 else args.trajectory_max_agents

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
            trajectory_max_agents=trajectory_max_agents,
            time_unit=args.time_unit,
        )

    if not args.skip_trajectory_time_evolution:
        trajectory_time_evolution_paths = generate_trajectory_time_evolution_images(
            summary=summary,
            project_root=PROJECT_ROOT,
            comparison_dir=out_dir,
            simulation_config=args.simulation_config,
            heuristics=args.heuristics,
            frame_bin_size=args.trajectory_time_bin_size,
            subdir=args.trajectory_time_subdir,
            trajectory_frame_stride=args.trajectory_frame_stride,
            trajectory_max_agents=trajectory_max_agents,
            time_unit=args.time_unit,
        )

    if not args.skip_congestion_gifs:
        congestion_gif_paths, congestion_highlight_paths = generate_congestion_gifs(
            summary=summary,
            project_root=PROJECT_ROOT,
            comparison_dir=out_dir,
            simulation_config=args.simulation_config,
            heuristics=args.heuristics,
            gif_subdir=args.congestion_gif_subdir,
            gif_max_frames=args.gif_max_frames,
            gif_frame_step=args.gif_frame_step,
            gif_fps=args.gif_fps,
            cutoff_radius=args.voronoi_cutoff_radius,
            cmap_name=args.gif_cmap,
            highlight_frames=args.congestion_highlight_frames,
            time_unit=args.time_unit,
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
        trajectory_time_evolution_paths=trajectory_time_evolution_paths,
        congestion_gif_paths=congestion_gif_paths,
        congestion_highlight_paths=congestion_highlight_paths,
    )

    print()
    print("Comparison finished.")
    print(f"Output directory: {out_dir}")
    print(f"Main metric: {main_metric}")

    if visual_pdf_paths:
        print("Visual PDFs:")
        for pdf_path in visual_pdf_paths:
            print(f"  - {pdf_path}")

    if trajectory_time_evolution_paths:
        print("Trajectory time-evolution images:")
        for png_path in trajectory_time_evolution_paths:
            print(f"  - {png_path}")

    if congestion_gif_paths:
        print("Congestion GIFs:")
        for gif_path in congestion_gif_paths:
            print(f"  - {gif_path}")

    if congestion_highlight_paths:
        print("Congestion frame snapshots:")
        for png_path in congestion_highlight_paths:
            print(f"  - {png_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())