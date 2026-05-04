import numpy as np
import pandas as pd
import sqlite3
import logging
from typing import Any
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Patch
from matplotlib.path import Path as MplPath
from shapely.geometry import Polygon, MultiPolygon
from matplotlib import cm
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

log = logging.getLogger(__name__)

GROUP_COLUMN_CANDIDATES = (
    "group_id", "group", "initial_group_id", "source_group_id", "origin_group_id", "cluster_id",
)

SPLIT_COLUMN_CANDIDATES = (
    "subgroup_id", "route_id", "route", "path_id", "assigned_route", "chosen_route",
    "target_id", "target", "target_node", "exit_id", "destination_id",
    "next_target", "next_node", "next_waypoint",
)


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    return next((column for column in candidates if column in df.columns), None)


def _format_plot_key(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _build_color_lookup(labels: list[str]) -> dict[str, Any]:
    unique_labels = list(dict.fromkeys(labels))
    if not unique_labels:
        return {}
    cmap_name = "tab20" if len(unique_labels) <= 20 else "hsv"
    cmap = plt.get_cmap(cmap_name, max(len(unique_labels), 1))
    return {label: cmap(index) for index, label in enumerate(unique_labels)}


def _prepare_trajectory_plot_labels(trajectory_df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str | None]:
    """Add labels for color-by-group trajectories, recoloring after detected splits."""
    if trajectory_df.empty:
        return trajectory_df.copy(), None, None

    df = trajectory_df.sort_values(["id", "frame"]).copy()
    group_col = _first_existing_column(df, GROUP_COLUMN_CANDIDATES)
    split_col = _first_existing_column(df, SPLIT_COLUMN_CANDIDATES)

    if group_col is None:
        df["__plot_group"] = "all agents"
    else:
        df["__plot_group"] = df[group_col].map(_format_plot_key)

    if split_col is None:
        df["__plot_split"] = df["__plot_group"]
        df["__plot_label"] = "Group " + df["__plot_group"]
        return df, group_col, split_col

    df["__plot_split"] = df[split_col].map(_format_plot_key)
    df["__plot_label"] = "Group " + df["__plot_group"]

    split_frames: dict[str, Any] = {}
    for group_value, group_df in df.groupby("__plot_group", sort=False):
        per_frame_unique_routes = group_df.groupby("frame")["__plot_split"].nunique(dropna=True)
        divided_frames = per_frame_unique_routes[per_frame_unique_routes > 1]
        if not divided_frames.empty:
            split_frames[group_value] = divided_frames.index.min()

    for group_value, split_frame in split_frames.items():
        mask = (df["__plot_group"] == group_value) & (df["frame"] >= split_frame)
        df.loc[mask, "__plot_label"] = (
            "Group "
            + df.loc[mask, "__plot_group"]
            + " → "
            + split_col
            + " "
            + df.loc[mask, "__plot_split"]
        )

    return df, group_col, split_col


def _plot_colored_trajectories(ax: plt.Axes, trajectory_df: pd.DataFrame) -> None:
    styled_df, group_col, split_col = _prepare_trajectory_plot_labels(trajectory_df)
    if styled_df.empty:
        return

    label_order = list(dict.fromkeys(styled_df["__plot_label"].tolist()))
    color_lookup = _build_color_lookup(label_order)

    for _, agent_df in styled_df.groupby("id", sort=False):
        agent_df = agent_df.sort_values("frame").copy()
        label_changed = agent_df["__plot_label"].ne(agent_df["__plot_label"].shift())
        agent_df["__plot_segment"] = label_changed.cumsum()

        for _, segment_df in agent_df.groupby("__plot_segment", sort=False):
            if len(segment_df) < 2:
                continue
            label = segment_df["__plot_label"].iloc[0]
            ax.plot(
                segment_df["pos_x"],
                segment_df["pos_y"],
                linewidth=0.85,
                alpha=0.62,
                color=color_lookup[label],
                zorder=4,
            )

    if split_col is not None:
        for _, group_df in styled_df.groupby("__plot_group", sort=False):
            per_frame_unique_routes = group_df.groupby("frame")["__plot_split"].nunique(dropna=True)
            divided_frames = per_frame_unique_routes[per_frame_unique_routes > 1]
            if divided_frames.empty:
                continue
            split_frame = divided_frames.index.min()
            split_points = group_df[group_df["frame"] == split_frame]
            ax.scatter(
                split_points["pos_x"],
                split_points["pos_y"],
                s=18,
                marker="x",
                linewidths=0.8,
                c="black",
                alpha=0.75,
                zorder=7,
            )

    # No legend is added for agent/group colors to keep the trajectory plot clean.

from evac_sim.db.sqlite_utils import read_trajectory_dataframe
from evac_sim.db.repositories.risk import get_risk_levels_by_frame

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

def _target_label(index: int) -> str:
    """Return Excel-like labels: A, B, ..., Z, AA, AB, ..."""
    label = ""
    number = index
    while True:
        number, remainder = divmod(number, 26)
        label = chr(ord("A") + remainder) + label
        if number == 0:
            return label
        number -= 1


def _polygon_label_point(poly: Polygon) -> tuple[float, float]:
    point = poly.representative_point()
    return float(point.x), float(point.y)


def _text_color_for_background(color: Any) -> str:
    r, g, b, *_ = mpl.colors.to_rgba(color)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "black" if luminance > 0.58 else "white"


def _get_specific_area_polygon(specific_areas: dict[Any, Any], area_id: Any) -> Polygon | None:
    area_key = area_id if area_id in specific_areas else str(area_id)
    if area_key not in specific_areas:
        return None
    return Polygon(specific_areas[area_key])


def _risk_style(risk_value: float, risk_threshold: float) -> tuple[str, str]:
    risk_value = float(risk_value)
    if risk_value <= 0.0:
        return "no_risk", "#f7f7f7"
    if risk_value < risk_threshold:
        return "risk_but_safe", "#f4a6c1"
    return "dangerous", "#6a1b9a"


def _overlay_target_area_identifiers(
    ax: plt.Axes,
    *,
    target_nodes: list[Any],
    specific_areas: dict[Any, Any],
    waypoints: dict[Any, Any],
) -> None:
    if not target_nodes:
        return

    target_cmap = plt.get_cmap("Set2", max(len(target_nodes), 1))
    for index, target in enumerate(target_nodes):
        label = _target_label(index)
        color = target_cmap(index)
        text_color = _text_color_for_background(color)
        poly = _get_specific_area_polygon(specific_areas, target)

        if poly is not None:
            x, y = poly.exterior.xy
            ax.fill(
                x,
                y,
                color=color,
                alpha=0.34,
                linewidth=0,
                zorder=2.2,
            )
            ax.plot(x, y, color=color, linewidth=1.2, alpha=0.95, zorder=3.2)
            label_x, label_y = _polygon_label_point(poly)
        elif str(target) in waypoints or target in waypoints:
            label_x, label_y = _get_waypoint_xy(waypoints, target)
        else:
            continue

        ax.text(
            label_x,
            label_y,
            label,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=text_color,
            bbox={
                "boxstyle": "circle,pad=0.32",
                "facecolor": color,
                "edgecolor": "black",
                "linewidth": 0.8,
                "alpha": 0.96,
            },
            zorder=9,
        )


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
            s=90,
            marker="*",
            c="#ffd54f",
            edgecolors="black",
            linewidths=0.7,
            alpha=1.0,
            zorder=7,
        )

def _overlay_danger_snapshot(
    fig,
    ax,
    *,
    specific_areas: dict[Any, Any],
    risk_by_area: dict[Any, float] | None,
    danger_frame: int | None,
    risk_threshold: float,
) -> None:
    if not risk_by_area:
        return

    risk_threshold = min(max(float(risk_threshold), 0.0), 1.0)
    legend_handles: dict[str, Patch] = {}
    legend_labels = {
        "no_risk": "no_risk (= 0)",
        "risk_but_safe": f"risk_but_safe (0 < risk < {risk_threshold:.2f})",
        "dangerous": f"dangerous (risk ≥ {risk_threshold:.2f})",
    }

    for area_id, risk_value in risk_by_area.items():
        poly = _get_specific_area_polygon(specific_areas, area_id)
        if poly is None:
            continue

        category, color = _risk_style(float(risk_value), risk_threshold)
        x, y = poly.exterior.xy
        ax.fill(
            x,
            y,
            color=color,
            alpha=0.46 if category != "no_risk" else 0.18,
            linewidth=0,
            zorder=1,
        )
        legend_handles.setdefault(
            category,
            Patch(facecolor=color, edgecolor="black", alpha=0.75, label=legend_labels[category]),
        )

    ordered_categories = ["no_risk", "risk_but_safe", "dangerous"]
    handles = [legend_handles[category] for category in ordered_categories if category in legend_handles]
    if handles:
        ax.legend(
            handles=handles,
            title=f"Risk at frame {danger_frame}",
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            frameon=True,
            fontsize=8,
            title_fontsize=9,
        )

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
    risk_threshold: float = 0.4,
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
            risk_threshold=risk_threshold,
        )

    _overlay_target_area_identifiers(
        ax,
        target_nodes=target_nodes,
        specific_areas=specific_areas,
        waypoints=waypoints,
    )

    if not trajectory_df.empty:
        _plot_colored_trajectories(ax, trajectory_df)

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
    specific_areas: dict[Any, Any],
    output_file: Path,
    title: str,
    cell_size: float = 0.5,
    density_percentile: float = 98.0,
) -> None:
    """Save a congestion-oriented density heatmap.

    The heatmap represents how many trajectory samples fall into each grid cell.
    A robust upper bound based on ``density_percentile`` prevents a few extreme
    cells from hiding medium congestion elsewhere.
    """
    polygon = getattr(walkable_area, "polygon", walkable_area)
    minx, miny, maxx, maxy = polygon.bounds

    fig, ax = plt.subplots(figsize=(10, 8))

    # Neutral background: enough contrast with congestion colors while keeping
    # the geometry readable.
    for poly in _iter_polygons(polygon):
        _draw_polygon_fill(ax, poly, facecolor="#f7f7f2", edgecolor="none", alpha=1.0)

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
        positive_values = masked_heatmap.compressed()
        positive_values = positive_values[positive_values > 0]

        if positive_values.size > 0:
            vmax = float(np.percentile(positive_values, density_percentile))
            vmax = max(vmax, 1.0)
        else:
            vmax = 1.0

        # Zero cells are transparent. Higher congestion becomes red/dark purple.
        congestion_cmap = LinearSegmentedColormap.from_list(
            "congestion_density",
            [
                (0.00, "#fff7bc"),
                (0.30, "#fec44f"),
                (0.55, "#fe9929"),
                (0.78, "#d95f0e"),
                (1.00, "#54278f"),
            ],
        )
        congestion_cmap.set_under((1, 1, 1, 0))

        norm = PowerNorm(gamma=0.65, vmin=0.5, vmax=vmax)
        mesh = ax.pcolormesh(
            xedges,
            yedges,
            masked_heatmap.T,
            shading="auto",
            cmap=congestion_cmap,
            norm=norm,
            alpha=0.88,
            zorder=1,
        )

        # Sidebar/colorbar with controlled height, aligned to the map.
        cax = inset_axes(
            ax,
            width="3.5%",
            height="90%",
            loc="center left",
            bbox_to_anchor=(1.03, 0.0, 1.0, 1.0),
            bbox_transform=ax.transAxes,
            borderpad=0.0,
        )
        cbar = fig.colorbar(mesh, cax=cax)
        cbar.ax.set_title("Congestion", pad=8, fontsize=9)
        cbar.set_label(
            "samples / grid cell",
            rotation=90,
            labelpad=10,
            fontsize=8,
        )
        cbar.ax.tick_params(labelsize=8)

    # Draw environment boundaries above the heatmap.
    _plot_environment_base(ax, walkable_area)

    # Show target areas exactly as in the trajectory plot: colored area + A/B/C.
    _overlay_target_area_identifiers(
        ax,
        target_nodes=target_nodes,
        specific_areas=specific_areas,
        waypoints=waypoints,
    )

    _overlay_start_and_target_markers(
        ax,
        trajectory_df=trajectory_df,
        waypoints=waypoints,
        target_nodes=target_nodes,
    )

    ax.set_xlabel("x (m)", fontsize=10)
    ax.set_ylabel("y (m)", fontsize=10, rotation=0, labelpad=18)
    ax.xaxis.label.set_rotation(0)
    ax.yaxis.label.set_rotation(0)
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
    case_name: str,
    danger_frame: int | None,
    images_dir: Path,
    env_name: str,
    mode: int,
    risk_threshold: float = 0.4,
) -> None:
    trajectory_df, fps = read_trajectory_dataframe(trajectory_file)
    log.info(
        "Generating visual artifacts | mode=%s fps=%.6f rows=%d",
        mode,
        fps,
        len(trajectory_df),
    )

    trajectory_png = images_dir / f"{env_name}_mode_{mode}_trajectories.png"
    density_png = images_dir / f"{env_name}_mode_{mode}_density.png"

    risk_by_area = None
    if danger_frame is not None:
        risk_conn = sqlite3.connect(str(risk_db_file))
        try:
            risk_by_area = get_risk_levels_by_frame(risk_conn, case_name, int(danger_frame))
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
        risk_threshold=risk_threshold,
    )

    _save_density_plot(
        trajectory_df=trajectory_df,
        walkable_area=walkable_area,
        output_file=density_png,
        waypoints=waypoints,
        target_nodes=target_nodes,
        specific_areas=specific_areas,
        title=f"{env_name} - mode {mode} congestion density",
    )
