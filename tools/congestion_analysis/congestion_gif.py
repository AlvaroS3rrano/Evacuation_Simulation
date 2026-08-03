from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd
import pedpy
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from .visualization import (
    RunVisualRecord,
    _common_terminal_frame,
    _create_2x2_figure,
    _frame_axis_label,
    _ordered_heuristics,
    _plot_polygon_boundaries,
    build_visual_records,
    choose_trajectory_db,
    load_case_config,
    resolve_case_fps,
)


def load_pedpy_trajectory(db_path: Path | None) -> pedpy.TrajectoryData | None:
    """Load raw per-agent per-frame positions from a JuPedSim trajectory sqlite file.

    Returns None if the file is missing or has no usable trajectory rows, rather than
    raising, so callers can fall back to a "no data" panel instead of aborting the case.
    """
    if db_path is None or not db_path.exists():
        return None

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(
                f'SELECT frame, id, pos_x AS {pedpy.X_COL}, pos_y AS {pedpy.Y_COL} '
                f'FROM "trajectory_data"',
                conn,
            )
            fps_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'fps'"
            ).fetchone()
    except sqlite3.Error:
        return None

    if df.empty:
        return None

    df[pedpy.FRAME_COL] = pd.to_numeric(df[pedpy.FRAME_COL], errors="coerce")
    df = df.dropna(subset=[pedpy.FRAME_COL, pedpy.X_COL, pedpy.Y_COL]).copy()
    if df.empty:
        return None

    df[pedpy.FRAME_COL] = df[pedpy.FRAME_COL].astype(int)
    df[pedpy.ID_COL] = df[pedpy.ID_COL].astype(int)

    fps = float(fps_row[0]) if fps_row and fps_row[0] is not None else 30.0

    return pedpy.TrajectoryData(data=df, frame_rate=fps)


def build_gif_frames(
    terminal_frame: int,
    *,
    max_frames: int,
    explicit_step: int | None,
) -> list[int]:
    """Pick a down-sampled list of frames spanning [0, terminal_frame].

    Voronoi density is only ever computed for these frames, which is what keeps the GIF
    affordable on runs with thousands of raw simulation frames and hundreds of agents.
    """
    terminal_frame = max(0, int(terminal_frame))

    if explicit_step:
        step = max(1, int(explicit_step))
    else:
        step = max(1, terminal_frame // max(1, int(max_frames)))

    frames = list(range(0, terminal_frame + 1, step))
    if not frames or frames[-1] != terminal_frame:
        frames.append(terminal_frame)

    return frames


def compute_case_voronoi(
    traj: pedpy.TrajectoryData,
    walkable_area: pedpy.WalkableArea,
    frames: Sequence[int],
    cutoff_radius: float | None,
) -> pd.DataFrame:
    """Compute per-agent Voronoi density, restricted to `frames` only.

    Filtering by frame *before* calling pedpy is safe: individual Voronoi cells only
    depend on agent positions within the same frame, never across frames.
    """
    frame_set = {int(frame) for frame in frames}
    subset = traj.data[traj.data[pedpy.FRAME_COL].isin(frame_set)][
        [pedpy.ID_COL, pedpy.FRAME_COL, pedpy.X_COL, pedpy.Y_COL]
    ].copy()

    if subset.empty:
        return subset.assign(**{pedpy.DENSITY_COL: pd.Series(dtype=float)})

    filtered_traj = pedpy.TrajectoryData(data=subset, frame_rate=traj.frame_rate)
    cutoff = pedpy.Cutoff(radius=cutoff_radius) if cutoff_radius else None

    return pedpy.compute_individual_voronoi_polygons(
        traj_data=filtered_traj,
        walkable_area=walkable_area,
        cut_off=cutoff,
    )


def _draw_congestion_frame(
    *,
    fig,
    axes: list,
    env,
    case_id: str,
    frame: int,
    selected_heuristics: Sequence[str],
    voronoi_tables: dict[str, pd.DataFrame | None],
    norm: Normalize,
    cmap_name: str,
    time_unit: str = "frame",
    fps: float | None = None,
) -> None:
    for idx, heuristic in enumerate(selected_heuristics[:4]):
        ax = axes[idx]
        ax.clear()
        _plot_polygon_boundaries(ax, env.walkable_area, linewidth=1.0, alpha=0.85)

        voronoi_df = voronoi_tables.get(heuristic)

        if voronoi_df is None:
            ax.text(
                0.5,
                0.5,
                "No trajectory data",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=11,
            )
        elif voronoi_df.empty or int(frame) not in set(voronoi_df[pedpy.FRAME_COL].unique()):
            ax.text(
                0.5,
                0.5,
                f"No data\n{_frame_axis_label(int(frame), time_unit=time_unit, fps=fps)}",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=10,
            )
        else:
            pedpy.plot_voronoi_cells(
                voronoi_data=voronoi_df,
                frame=int(frame),
                walkable_area=env.walkable_area,
                color_by_column=pedpy.DENSITY_COL,
                axes=ax,
                show_colorbar=False,
                vmin=norm.vmin,
                vmax=norm.vmax,
                cmap=cmap_name,
            )

        ax.set_title(heuristic)
        ax.set_aspect("equal", adjustable="box")

    for idx in range(len(selected_heuristics[:4]), 4):
        axes[idx].axis("off")

    fig.suptitle(
        f"{case_id} | congestion (Voronoi density) | "
        f"{_frame_axis_label(int(frame), time_unit=time_unit, fps=fps)}",
        fontsize=14,
    )


def _new_congestion_figure(*, case_id: str, used_config_name: str, norm: Normalize, cmap_name: str):
    fig, axes = _create_2x2_figure(
        title=f"{case_id} | congestion (Voronoi density) | config={used_config_name}",
        with_sidebar=True,
    )
    cax = fig.add_axes([0.87, 0.18, 0.018, 0.64])
    cbar = fig.colorbar(
        ScalarMappable(norm=norm, cmap=plt.get_cmap(cmap_name)),
        cax=cax,
    )
    cbar.set_label("Voronoi density [agents/m$^2$]")
    return fig, axes


def generate_congestion_gifs(
    *,
    summary: pd.DataFrame,
    project_root: Path,
    comparison_dir: Path,
    simulation_config: Path | None,
    heuristics: Sequence[str],
    gif_subdir: str = "congestion_gifs",
    gif_max_frames: int = 60,
    gif_frame_step: int | None = None,
    gif_fps: int = 8,
    cutoff_radius: float | None = None,
    cmap_name: str = "YlGn",
    highlight_frames: Sequence[int] | None = None,
    time_unit: str = "frame",
) -> tuple[list[Path], list[Path]]:
    """Generate one Voronoi-density congestion GIF per case (one panel per heuristic).

    If `highlight_frames` is given, also saves a standalone snapshot PNG per case for
    each requested frame (independent of whichever frames the GIF itself sampled),
    reusing the exact same renderer so the snapshot matches the GIF's visual style.
    """
    from evac_sim.envs.environment_factory import select_environment

    base_dir = comparison_dir / gif_subdir
    base_dir.mkdir(parents=True, exist_ok=True)

    records = build_visual_records(summary)
    by_case: dict[str, dict[str, RunVisualRecord]] = {}

    for record in records:
        by_case.setdefault(record.case_id, {})[record.heuristic] = record

    gif_paths: list[Path] = []
    highlight_paths: list[Path] = []

    for case_id in sorted(by_case):
        case_records = by_case[case_id]
        selected_heuristics = _ordered_heuristics(
            available=set(case_records),
            requested=heuristics,
        )

        try:
            case_cfg, used_config = load_case_config(
                project_root=project_root,
                case_id=case_id,
                simulation_config=simulation_config,
            )
            env = select_environment(case_cfg["environment"])
        except Exception as exc:
            print(f"[congestion-gif] SKIP case={case_id} reason={exc}")
            continue

        case_time_unit = time_unit
        case_fps: float | None = None
        if time_unit == "seconds":
            case_fps = resolve_case_fps(case_records)
            if case_fps is None:
                print(
                    f"[congestion-gif] WARN case={case_id} time_unit=seconds requested but "
                    "fps unavailable; falling back to frame"
                )
                case_time_unit = "frame"

        traj_tables: dict[str, pedpy.TrajectoryData | None] = {}

        for heuristic in selected_heuristics:
            record = case_records.get(heuristic)

            if record is None:
                traj_tables[heuristic] = None
                continue

            try:
                db_path = choose_trajectory_db(record.run_dir)
                traj_tables[heuristic] = load_pedpy_trajectory(db_path)
            except Exception as exc:
                print(f"[congestion-gif] WARN case={case_id} heuristic={heuristic} error={exc}")
                traj_tables[heuristic] = None

        frame_source = {
            heuristic: traj.data
            for heuristic, traj in traj_tables.items()
            if traj is not None
        }
        terminal_frame = _common_terminal_frame(frame_source)

        if terminal_frame is None:
            print(f"[congestion-gif] SKIP case={case_id} reason=no trajectory data for any heuristic")
            continue

        gif_frames = build_gif_frames(
            terminal_frame,
            max_frames=gif_max_frames,
            explicit_step=gif_frame_step,
        )

        voronoi_tables: dict[str, pd.DataFrame | None] = {}

        for heuristic in selected_heuristics:
            traj = traj_tables.get(heuristic)

            if traj is None:
                voronoi_tables[heuristic] = None
                continue

            try:
                voronoi_tables[heuristic] = compute_case_voronoi(
                    traj,
                    env.walkable_area,
                    gif_frames,
                    cutoff_radius,
                )
            except Exception as exc:
                print(f"[congestion-gif] WARN voronoi case={case_id} heuristic={heuristic} error={exc}")
                voronoi_tables[heuristic] = None

        vmax_candidates = [
            float(df[pedpy.DENSITY_COL].max())
            for df in voronoi_tables.values()
            if df is not None and not df.empty
        ]
        # Fixed across every frame and heuristic panel (not renormalized per frame), so the
        # animation is honestly comparable over time instead of auto-stretching the palette.
        norm = Normalize(vmin=0.0, vmax=max(vmax_candidates) if vmax_candidates else 1.0)

        case_dir = base_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        fig, axes = _new_congestion_figure(
            case_id=case_id,
            used_config_name=used_config.name,
            norm=norm,
            cmap_name=cmap_name,
        )

        def _update(frame: int) -> None:
            _draw_congestion_frame(
                fig=fig,
                axes=axes,
                env=env,
                case_id=case_id,
                frame=frame,
                selected_heuristics=selected_heuristics,
                voronoi_tables=voronoi_tables,
                norm=norm,
                cmap_name=cmap_name,
                time_unit=case_time_unit,
                fps=case_fps,
            )

        anim = FuncAnimation(fig, _update, frames=gif_frames, blit=False)
        gif_path = case_dir / f"{case_id}_congestion.gif"
        anim.save(gif_path, writer=PillowWriter(fps=gif_fps))
        plt.close(fig)

        gif_paths.append(gif_path)
        print(f"Congestion GIF: {gif_path}")

        if not highlight_frames:
            continue

        requested = {int(frame) for frame in highlight_frames}
        in_range = sorted(frame for frame in requested if 0 <= frame <= terminal_frame)
        out_of_range = sorted(requested - set(in_range))

        if out_of_range:
            print(
                f"[congestion-gif] case={case_id} highlight frames out of range "
                f"[0, {terminal_frame}] skipped: {out_of_range}"
            )

        for highlight_frame in in_range:
            highlight_voronoi: dict[str, pd.DataFrame | None] = {}

            for heuristic in selected_heuristics:
                traj = traj_tables.get(heuristic)

                if traj is None:
                    highlight_voronoi[heuristic] = None
                    continue

                try:
                    highlight_voronoi[heuristic] = compute_case_voronoi(
                        traj,
                        env.walkable_area,
                        [highlight_frame],
                        cutoff_radius,
                    )
                except Exception as exc:
                    print(
                        f"[congestion-gif] WARN highlight case={case_id} heuristic={heuristic} "
                        f"frame={highlight_frame} error={exc}"
                    )
                    highlight_voronoi[heuristic] = None

            snap_fig, snap_axes = _new_congestion_figure(
                case_id=case_id,
                used_config_name=used_config.name,
                norm=norm,
                cmap_name=cmap_name,
            )

            _draw_congestion_frame(
                fig=snap_fig,
                axes=snap_axes,
                env=env,
                case_id=case_id,
                frame=highlight_frame,
                selected_heuristics=selected_heuristics,
                voronoi_tables=highlight_voronoi,
                norm=norm,
                cmap_name=cmap_name,
                time_unit=case_time_unit,
                fps=case_fps,
            )

            if case_time_unit == "seconds" and case_fps:
                snap_suffix = f"t{highlight_frame / case_fps:.1f}s"
            else:
                snap_suffix = f"frame_{highlight_frame:06d}"

            snap_path = case_dir / f"{case_id}_{snap_suffix}.png"
            snap_fig.savefig(snap_path, dpi=150)
            plt.close(snap_fig)

            highlight_paths.append(snap_path)
            print(f"Congestion frame snapshot: {snap_path}")

    return gif_paths, highlight_paths
