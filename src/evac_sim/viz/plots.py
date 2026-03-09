import numpy as np
import pandas as pd
import sqlite3
import logging
from typing import Any
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.path import Path as MplPath
from shapely.geometry import Polygon, MultiPolygon
from matplotlib import cm
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap

log = logging.getLogger(__name__)

from evac_sim.db.sqlite_utils import read_trajectory_dataframe
from evac_sim.db.danger_sim_db_manager import get_risk_levels_by_frame

def _draw_polygon_outline(ax: plt.Axes, poly: Polygon, *, edgecolor: str = "black", linewidth: float = 1.0, alpha: float = 1.0) -> None:
    x, y = poly.exterior.xy
    ax.plot(x, y, color=edgecolor, linewidth=linewidth, alpha=alpha)
    for interior in poly.interiors:
        ix, iy = interior.xy
        ax.plot(ix, iy, color=edgecolor, linewidth=linewidth, alpha=alpha)


def _draw_polygon_fill(ax: plt.Axes, poly: Polygon, *, facecolor: str = "lightgray", edgecolor: str = "none", alpha: float = 1.0) -> None:
    exterior = np.asarray(poly.exterior.coords)
    patch = MplPolygon(
        exterior,
        closed=True,
        facecolor=facecolor,
        edgecolor=edgecolor,
        alpha=alpha,
    )
    ax.add_patch(patch)


def _iter_polygons(geom: Any) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    raise TypeError(f"Unsupported geometry type for plotting: {type(geom)!r}")


def _plot_environment_base(ax: plt.Axes, walkable_area: Any) -> None:
    polygon = getattr(walkable_area, "polygon", walkable_area)
    for poly in _iter_polygons(polygon):
        _draw_polygon_outline(ax, poly, edgecolor="black", linewidth=1.5, alpha=0.9)

    minx, miny, maxx, maxy = polygon.bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _get_waypoint_xy(waypoints: dict[Any, Any], node_id: Any) -> tuple[float, float]:
    waypoint = waypoints[str(node_id)] if str(node_id) in waypoints else waypoints[node_id]
    coords = waypoint[0]
    return float(coords[0]), float(coords[1])


def _starting_positions_from_trajectory(trajectory_df: pd.DataFrame) -> pd.DataFrame:
    if trajectory_df.empty:
        return pd.DataFrame(columns=["id", "pos_x", "pos_y"])

    ordered = trajectory_df.sort_values(["id", "frame"]).copy()
    return ordered.groupby("id", as_index=False).first()[["id", "pos_x", "pos_y"]]


def _overlay_start_and_target_markers(
    ax: plt.Axes,
    *,
    trajectory_df: pd.DataFrame,
    waypoints: dict[Any, Any],
    target_nodes: list[Any],
) -> None:
    start_df = _starting_positions_from_trajectory(trajectory_df)
    if not start_df.empty:
        ax.scatter(
            start_df["pos_x"],
            start_df["pos_y"],
            s=18,
            marker="o",
            c="black",
            edgecolors="white",
            linewidths=0.35,
            alpha=0.95,
            zorder=6,
        )

    target_xy = [
        _get_waypoint_xy(waypoints, target)
        for target in target_nodes
        if str(target) in waypoints or target in waypoints
    ]
    if target_xy:
        tx, ty = zip(*target_xy)
        ax.scatter(
            tx,
            ty,
            s=140,
            marker="*",
            c="#ffd54f",
            edgecolors="black",
            linewidths=0.8,
            alpha=1.0,
            zorder=7,
        )
        for target, (x, y) in zip(target_nodes, target_xy):
            ax.annotate(
                str(target),
                (x, y),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="black",
                zorder=8,
            )


def _overlay_danger_snapshot(
    fig,
    ax,
    *,
    specific_areas: dict[Any, Any],
    risk_by_area: dict[Any, float] | None,
    danger_frame: int | None,
) -> None:
    if not risk_by_area:
        return

    norm_risk = mpl.colors.Normalize(vmin=0.0, vmax=1.0)
    risk_cmap = LinearSegmentedColormap.from_list(
        "pink_purple",
        ["white", "pink", "purple"],
    )
    sm_risk = cm.ScalarMappable(cmap=risk_cmap, norm=norm_risk)
    sm_risk.set_array([])

    for area_id, risk_value in risk_by_area.items():
        area_key = area_id if area_id in specific_areas else str(area_id)
        if area_key not in specific_areas:
            continue

        poly = Polygon(specific_areas[area_key])
        x, y = poly.exterior.xy
        ax.fill(
            x,
            y,
            color=risk_cmap(norm_risk(float(risk_value))),
            alpha=0.5,
            linewidth=0,
            zorder=1,
        )

    cbar = fig.colorbar(sm_risk, ax=ax, fraction=0.045, pad=0.04)
    cbar.set_label(f"danger at frame {danger_frame}")
    cbar.set_ticks(np.arange(0.0, 1.01, 0.1))
    cbar.ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))


def _save_trajectory_plot(
    *,
    trajectory_df: pd.DataFrame,
    walkable_area: Any,
    waypoints: dict[Any, Any],
    target_nodes: list[Any],
    specific_areas: dict[Any, Any],
    output_file: Path,
    title: str,
    risk_by_area: dict[Any, float] | None = None,
    danger_frame: int | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 8))
    _plot_environment_base(ax, walkable_area)

    if risk_by_area:
        _overlay_danger_snapshot(
            fig,
            ax,
            specific_areas=specific_areas,
            risk_by_area=risk_by_area,
            danger_frame=danger_frame,
        )

    if not trajectory_df.empty:
        for _, group_df in trajectory_df.sort_values(["id", "frame"]).groupby("id"):
            ax.plot(
                group_df["pos_x"],
                group_df["pos_y"],
                linewidth=0.6,
                alpha=0.38,
                color="#1f1f1f",
                zorder=4,
            )

    _overlay_start_and_target_markers(
        ax,
        trajectory_df=trajectory_df,
        waypoints=waypoints,
        target_nodes=target_nodes,
    )

    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close(fig)


def _save_density_plot(
    *,
    trajectory_df: pd.DataFrame,
    walkable_area: Any,
    waypoints: dict[Any, Any],
    target_nodes: list[Any],
    output_file: Path,
    title: str,
    cell_size: float = 0.5,
) -> None:
    polygon = getattr(walkable_area, "polygon", walkable_area)
    minx, miny, maxx, maxy = polygon.bounds

    fig, ax = plt.subplots(figsize=(10, 8))

    for poly in _iter_polygons(polygon):
        _draw_polygon_fill(ax, poly, facecolor="white", edgecolor="none", alpha=1.0)

    if not trajectory_df.empty:
        x_edges = np.arange(minx, maxx + cell_size, cell_size)
        y_edges = np.arange(miny, maxy + cell_size, cell_size)

        heatmap, xedges, yedges = np.histogram2d(
            trajectory_df["pos_x"].to_numpy(dtype=float),
            trajectory_df["pos_y"].to_numpy(dtype=float),
            bins=[x_edges, y_edges],
        )

        x_centers = (xedges[:-1] + xedges[1:]) / 2.0
        y_centers = (yedges[:-1] + yedges[1:]) / 2.0
        xx, yy = np.meshgrid(x_centers, y_centers, indexing="ij")
        points = np.column_stack([xx.ravel(), yy.ravel()])

        mask = np.zeros(points.shape[0], dtype=bool)
        for poly in _iter_polygons(polygon):
            exterior_path = MplPath(np.asarray(poly.exterior.coords))
            inside = exterior_path.contains_points(points)
            if poly.interiors:
                for interior in poly.interiors:
                    inside &= ~MplPath(np.asarray(interior.coords)).contains_points(points)
            mask |= inside

        masked_heatmap = np.ma.masked_where(~mask.reshape(heatmap.shape), heatmap)

        mesh = ax.pcolormesh(
            xedges,
            yedges,
            masked_heatmap.T,
            shading="auto",
            cmap="magma",
            alpha=0.9,
            zorder=1,
        )
        cbar = fig.colorbar(mesh, ax=ax)
        cbar.set_label("trajectory sample density")

    _plot_environment_base(ax, walkable_area)

    _overlay_start_and_target_markers(
        ax,
        trajectory_df=trajectory_df,
        waypoints=waypoints,
        target_nodes=target_nodes,
    )

    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_mode_visual_artifacts(
    *,
    trajectory_file: Path,
    walkable_area: Any,
    waypoints: dict[Any, Any],
    target_nodes: list[Any],
    specific_areas: dict[Any, Any],
    risk_db_file: Path,
    danger_frame: int | None,
    artifacts_dir: Path,
    env_name: str,
    mode: int,
) -> None:
    trajectory_df, fps = read_trajectory_dataframe(trajectory_file)
    log.info(
        "Generating visual artifacts | mode=%s fps=%.6f rows=%d",
        mode,
        fps,
        len(trajectory_df),
    )

    trajectory_png = artifacts_dir / f"{env_name}_mode_{mode}_trajectories.png"
    density_png = artifacts_dir / f"{env_name}_mode_{mode}_density.png"

    risk_by_area = None
    if danger_frame is not None:
        risk_conn = sqlite3.connect(str(risk_db_file))
        try:
            risk_by_area = get_risk_levels_by_frame(risk_conn, int(danger_frame))
        finally:
            risk_conn.close()

    _save_trajectory_plot(
        trajectory_df=trajectory_df,
        walkable_area=walkable_area,
        waypoints=waypoints,
        target_nodes=target_nodes,
        specific_areas=specific_areas,
        output_file=trajectory_png,
        title=(
            f"{env_name} - mode {mode} trajectories"
            + (f" - danger frame {danger_frame}" if danger_frame is not None else "")
        ),
        risk_by_area=risk_by_area,
        danger_frame=danger_frame,
    )

    _save_density_plot(
        trajectory_df=trajectory_df,
        walkable_area=walkable_area,
        output_file=density_png,
        waypoints=waypoints,
        target_nodes=target_nodes,
        title=f"{env_name} - mode {mode} density",
    )
