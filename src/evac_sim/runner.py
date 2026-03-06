from __future__ import annotations

import datetime as dt
import json
import logging
import platform
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import networkx as nx
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.path import Path as MplPath
from shapely.geometry import Polygon, MultiPolygon
from matplotlib import cm
from matplotlib.ticker import FormatStrFormatter

import jupedsim as jps
import numpy as np
import yaml
import pandas as pd
import gc
from matplotlib.colors import LinearSegmentedColormap

import evac_sim.envs.environment as pol
from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.core.risk_simulation_values import RiskSimulationValues
from evac_sim.core.simulation_config import SimulationConfig
from evac_sim.db.danger_sim_db_manager import create_risk_table, get_risk_levels_by_frame
from evac_sim.db.group_path_db_manager import create_group_path_table
from evac_sim.db.paths_db_manager import create_paths_table
from evac_sim.db.simulation_results_db_manager import (
    create_tables,
    write_experiment,
    write_experiment_metrics,
    export_experiments_to_csv,
    export_experiment_metrics_to_csv,
)
from evac_sim.db.agent_area_db_manager import (
    create_agent_area_table,
    read_agent_area_data,
    get_average_normalized_risk_exposure_by_group,
)
from evac_sim.db.group_path_db_manager import read_group_path_data
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.risk.risk_simulation import simulate_risk
from evac_sim.routing.decision_policies import compute_alternative_path
from evac_sim.simulation.simulation_manager import run_agent_simulation, set_agents_in_simulation

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunPaths:
    project_root: Path
    config_file: Path
    run_dir: Path
    logs_dir: Path
    artifacts_dir: Path


def _git_commit_hash(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"

def _p90(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.array(values, dtype=float), 90))

def _compute_times_from_trajectory_sqlite(
    trajectory_db_file: Path,
    agent_ids: list[int],
) -> list[float]:
    """
    Compute per-agent evacuation times from the JuPedSim trajectory SQLite output,
    using the FPS written by JuPedSim into the trajectory database metadata.
    """
    if not agent_ids:
        return []

    conn = sqlite3.connect(str(trajectory_db_file))
    try:
        tables_df = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            conn,
        )
        table_names = set(tables_df["name"].tolist())

        trajectory_table = next(
            (name for name in ["trajectory_data", "trajectory", "trajectories"] if name in table_names),
            None,
        )

        if trajectory_table is None:
            raise RuntimeError(
                f"No trajectory table found in {trajectory_db_file}. "
                f"Available tables: {sorted(table_names)}"
            )

        fps = _read_sqlite_fps(conn)
        ids_str = ",".join(str(int(a)) for a in agent_ids)

        query = f"""
            SELECT id, MAX(frame) AS max_frame
            FROM {trajectory_table}
            WHERE id IN ({ids_str})
            GROUP BY id
        """

        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        return []

    return (df["max_frame"].astype(float) / fps).tolist()

def _path_cost(graph: nx.Graph, path: list[Any]) -> float:
    if not path or len(path) < 2:
        return 0.0

    total_cost = 0.0
    for u, v in zip(path, path[1:]):
        if not graph.has_edge(u, v):
            raise RuntimeError(
                f"Edge ({u}, {v}) not found while computing cost for path {path}"
            )

        edge_data = graph[u][v]
        cost = edge_data.get("cost")
        if cost is None:
            raise RuntimeError(
                f"Edge ({u}, {v}) is missing the 'cost' attribute for path {path}"
            )

        total_cost += float(cost)

    return total_cost


def _read_sqlite_fps(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT value FROM metadata WHERE key = ?", ("fps",)).fetchone()
    if row is None:
        raise RuntimeError("Trajectory DB missing metadata.fps")
    return float(row[0])


def _read_trajectory_dataframe(trajectory_db_file: Path) -> tuple[pd.DataFrame, float]:
    conn = sqlite3.connect(str(trajectory_db_file))
    try:
        tables_df = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            conn,
        )
        table_names = set(tables_df["name"].tolist())

        trajectory_table = next(
            (name for name in ["trajectory_data", "trajectory", "trajectories"] if name in table_names),
            None,
        )
        if trajectory_table is None:
            raise RuntimeError(
                f"No trajectory table found in {trajectory_db_file}. Available tables: {sorted(table_names)}"
            )

        fps = _read_sqlite_fps(conn)
        df = pd.read_sql_query(
            f"SELECT frame, id, pos_x, pos_y FROM {trajectory_table}",
            conn,
        )
    finally:
        conn.close()

    if not df.empty:
        df["frame"] = df["frame"].astype(float)
        df["id"] = df["id"].astype(int)
        df["pos_x"] = df["pos_x"].astype(float)
        df["pos_y"] = df["pos_y"].astype(float)

    return df, fps


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


def _generate_mode_visual_artifacts(
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
    trajectory_df, fps = _read_trajectory_dataframe(trajectory_file)
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



def _compute_group_metrics(
    *,
    graph: nx.Graph,
    group_path_df: pd.DataFrame,
    agent_area_conn: sqlite3.Connection,
    group_id: Any,
    agent_ids: list[int],
    per_agent_times: list[float],
) -> dict[str, Any]:
    gdf = group_path_df[group_path_df["group_id"].astype(str) == str(group_id)].copy()
    n_records = int(len(gdf))

    mean_remaining_path_risk = float(gdf["est_risk_mean"].mean()) if n_records else 0.0
    remaining_path_risk_var = float(gdf["est_risk_var"].mean()) if n_records else 0.0

    if n_records and "next_path" in gdf.columns:
        avg_path_cost = float(
            gdf["next_path"].apply(
                lambda p: _path_cost(graph, p) if isinstance(p, list) else 0.0
            ).mean()
        )
    else:
        avg_path_cost = 0.0

    cumulative_risk_exposure = float(
        get_average_normalized_risk_exposure_by_group(agent_area_conn, agent_ids)
    )

    if per_agent_times:
        min_time = float(min(per_agent_times))
        avg_time = float(sum(per_agent_times) / len(per_agent_times))
        median_time = float(np.median(np.array(per_agent_times, dtype=float)))
        p90_time = _p90(per_agent_times)
        max_time = float(max(per_agent_times))
    else:
        min_time = avg_time = median_time = p90_time = max_time = 0.0

    return {
        "n_records": n_records,
        "mean_remaining_path_risk": mean_remaining_path_risk,
        "remaining_path_risk_var": remaining_path_risk_var,
        "cumulative_risk_exposure": cumulative_risk_exposure,
        "avg_path_cost": avg_path_cost,
        "min_time": min_time,
        "avg_time": avg_time,
        "median_time": median_time,
        "p90_time": p90_time,
        "max_time": max_time,
    }

def _make_run_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    runs_dir = project_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final = runs_dir / f"{stamp}_{case_id}"
    final.mkdir(parents=True, exist_ok=True)
    return final


def _load_case(config_file: Path, case_id: str) -> dict[str, Any]:
    with config_file.open("r", encoding="utf-8") as f:
        all_configs = yaml.safe_load(f)

    if case_id not in all_configs:
        available = ", ".join(sorted(all_configs.keys()))
        raise KeyError(f"case_id '{case_id}' not found in {config_file}. Available: {available}")

    cfg = all_configs[case_id]
    if not isinstance(cfg, dict):
        raise TypeError(f"case '{case_id}' must be a mapping/dict in YAML")
    return cfg


def _setup_run_logging(run_dir: Path, verbose: bool) -> None:
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "run.log"

    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
        force=True,
    )


def _prepare_paths(
    project_root: Path, config_name: str, case_id: str, out_dir: Optional[Path]
) -> RunPaths:
    config_file = project_root / "configs" / config_name
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    run_dir = _make_run_dir(project_root, case_id, out_dir)
    logs_dir = run_dir / "logs"
    artifacts_dir = run_dir / "artifacts"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
    )


def _select_environment(name: str):
    environments = {
        "cruise_ship": pol.get_cruise_ship,
        "cruise_ship_v2": pol.get_cruise_ship_v2,
        "mall": pol.get_mall,
        "theme_park": pol.get_theme_park,
        "simple_3x3": pol.get_simple_3x3,
        "comparing_algorithms": pol.get_comparing_algorithms_pol,
        "corridor": pol.get_corridor_environment,
    }
    if name not in environments:
        raise ValueError(f"Unknown environment '{name}'. Available: {list(environments.keys())}")
    return environments[name]()


def _init_db_connection(
    db_file: Path,
    create_fn: Optional[Callable[[sqlite3.Connection], None]] = None,
) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    if create_fn is not None:
        create_fn(conn)
    return conn


def _run_experiment_from_case(cfg: dict[str, Any], paths: RunPaths, case_id: str) -> None:
    # --- Load environment ---
    env = _select_environment(cfg["environment"])

    env_name = env.name
    walkable_area = env.walkable_area
    obstacles = env.obstacles
    targets = cfg["targets"]
    sources = cfg["sources"]
    total_agents = cfg["agents"]
    waypoints = env.waypoints
    G = env.graph
    specific_areas = env.specific_areas

    # --- Modes ---
    mode_type = int(cfg.get("mode_type", 0))
    mode_indices = {
        0: [0, 1, 2, 3],
        1: [0, 1],
        2: [0, 1],
        3: [2, 3],
        4: [2],
    }
    if mode_type not in mode_indices:
        raise ValueError(f"Unsupported mode_type: {mode_type}")
    modes = mode_indices[mode_type]

    awareness_levels_per_group = [0, 1, 0, 1]
    algorithm_per_group = [0, 0, 1, 1]

    # --- Parameters ---
    risk_seed = int(cfg["risk_seed"])
    risk_iterations = int(cfg["risk_iterations"])
    risk_increase_chance = float(cfg["risk_increase_chance"])
    propagation_threshold = float(cfg["propagation_threshold"])
    risk_threshold = float(cfg["risk_threshold"])
    gamma = float(cfg["gamma"])
    stairs_max_speed = float(cfg["stairs_max_speed"])
    normal_max_speed = float(cfg["normal_max_speed"])

    every_nth_frame_simulation = int(cfg["every_nth_frame_simulation"])
    every_nth_frame_animation = int(cfg["every_nth_frame_animation"])
    danger_visualization_frame = cfg.get("danger_visualization_frame", cfg.get("danger_frame", None))
    if danger_visualization_frame is not None:
        danger_visualization_frame = int(danger_visualization_frame)

    starting_risks = [tuple(x) for x in (cfg.get("starting_risks", []) or [])]
    risk_overrides = [tuple(x) for x in (cfg.get("risk_overrides", []) or [])]

    # --- Files inside run artifacts ---
    risk_db_file = paths.artifacts_dir / f"{env_name}_risks.db"
    paths_db_file = paths.artifacts_dir / f"{env_name}_paths.db"
    group_paths_db_file = paths.artifacts_dir / f"{env_name}_group_paths.db"
    results_db_file = paths.artifacts_dir / f"{env_name}_results.db"

    # --- DB connections ---
    risk_db_conn = _init_db_connection(risk_db_file, create_risk_table)
    paths_conn = _init_db_connection(paths_db_file, create_paths_table)
    group_path_conn = _init_db_connection(group_paths_db_file, create_group_path_table)
    results_db_conn = _init_db_connection(results_db_file, create_tables)

    # --- Prepare targets/areas ---
    pol.set_targets(targets, env)

    # --- Allocate agent positions per source ---
    positions: dict[str, np.ndarray] = {}
    for i, source in enumerate(sources):
        positions[source] = jps.distribute_by_number(
            polygon=specific_areas[source],
            number_of_agents=total_agents[i],
            distance_to_agents=0.4,
            distance_to_polygon=0.5,
            seed=45131502,
        )

    # --- Risk simulation (random layout always, like notebook) ---
    risk_values = RiskSimulationValues(
        risk_iterations,
        risk_increase_chance,
        propagation_threshold,
        starting_risks,
        risk_overrides,
    )

    log.info("Simulating risks: iterations=%s seed=%s", risk_iterations, risk_seed)
    simulate_risk(
        risk_values,
        every_nth_frame_animation,
        G,
        targets,
        risk_db_conn,
        risk_seed,
    )
    risk_first_frame = get_risk_levels_by_frame(risk_db_conn, 0)

    # --- EnvironmentInfo ---
    env_info = EnvironmentInfo(G, paths_conn, floor_number=env.floor_number)
    if env.floor_number > 1:
        env_info.floors = env.floors
        env_info.floor_connecting_nodes = env.floor_connecting_nodes

    # --- Run per mode ---
    for mode in modes:
        log.info("Mode start | mode=%s env=%s case=%s", mode, env_name, cfg.get("name", "unknown"))

        trajectory_file = paths.artifacts_dir / f"{env_name}_mode_{mode}.sqlite"

        simulation = jps.Simulation(
            model=jps.CollisionFreeSpeedModel(
                strength_neighbor_repulsion=2.6,
                range_neighbor_repulsion=0.1,
                range_geometry_repulsion=0.05,
            ),
            geometry=walkable_area.polygon,
            trajectory_writer=jps.SqliteTrajectoryWriter(
                output_file=Path(trajectory_file),
                every_nth_frame=every_nth_frame_simulation,
            ),
        )

        # Per-mode DBs (avoid mixing data across modes)
        agent_area_db_file = paths.artifacts_dir / f"agent_area_{env_name}_mode_{mode}.db"
        agent_area_conn = sqlite3.connect(str(agent_area_db_file))
        create_agent_area_table(agent_area_conn)

        group_paths_db_file_mode = paths.artifacts_dir / f"{env_name}_group_paths_mode_{mode}.db"
        group_path_conn_mode = _init_db_connection(group_paths_db_file_mode, create_group_path_table)

        exit_ids: dict[Any, Any] = {}
        for area_id in targets:
            exit_ids[area_id] = simulation.add_exit_stage(specific_areas[area_id])

        waypoints_ids: dict[Any, Any] = {}
        for node, (waypoint, distance) in waypoints.items():
            waypoints_ids[node] = simulation.add_waypoint_stage(waypoint, distance)

        agent_groups: dict[str, AgentGroup] = {}

        for i, source in enumerate(sources):
            if mode_type == 1:
                group = AgentGroup(None, None, None, i, mode)
            else:
                group = AgentGroup(
                    None,
                    None,
                    None,
                    algorithm_per_group[mode],
                    awareness_levels_per_group[mode],
                )

            path = compute_alternative_path(
                targets,
                group,
                env_info,
                source,
                risk_per_node=risk_first_frame,
                gamma=gamma,
            )

            journeys_ids = set_journeys(simulation, source, [path], waypoints_ids, exit_ids)
            journey_id, best_path_source = journeys_ids[source][0]
            next_node = best_path_source[1]
            first_waypoint_id = waypoints_ids[next_node]

            agents = set_agents_in_simulation(
                simulation,
                positions[source],
                journey_id,
                first_waypoint_id,
                normal_max_speed,
            )

            agent_ids = [a.id if hasattr(a, "id") else int(a) for a in agents]

            group.path = path
            group.current_nodes = {agent_id: path[0] for agent_id in agent_ids}
            group.agents = agent_ids

            # Keep a stable copy for post-run metrics
            group.initial_agent_ids = list(agent_ids)

            agent_groups[source] = group

        sim_cfg = SimulationConfig(
            simulation,
            every_nth_frame_simulation,
            every_nth_frame_animation,
            waypoints_ids,
            exit_ids,
            gamma,
            normal_max_speed,
            stairs_max_speed,
        )

        # Use a fresh risk DB connection per mode
        risk_db_conn_mode = sqlite3.connect(str(risk_db_file))

        try:
            run_agent_simulation(
                sim_cfg,
                cfg.get("log_every_frames", 10),
                agent_groups,
                env_info,
                risk_db_conn_mode,
                agent_area_conn,
                group_path_conn_mode,
                threshold=risk_threshold,
            )
        except Exception:
            log.exception("Simulation failed | mode=%s", mode)
            raise
        finally:
            risk_db_conn_mode.close()

        # Force JuPedSim objects to be released so the trajectory SQLite file is finalized
        del sim_cfg
        del simulation
        gc.collect()

        # --- Write results only if simulation succeeded ---
        case_name_mode = f"{case_id}_mode_{mode}"

        experiment_id = write_experiment(
            results_db_conn,
            case_name=case_name_mode,
            risk_nodes=targets,
            source_nodes=sources,
            agents_per_source=total_agents,
            random_seed=risk_seed,
        )

        group_path_df = read_group_path_data(group_path_conn_mode)

        for group_id, group in agent_groups.items():
            algorithm = "Centrality" if getattr(group, "algorithm", 0) == 1 else "Efficient"
            awareness = float(getattr(group, "awareness_level", 0))

            initial_agent_ids = [int(a) for a in getattr(group, "initial_agent_ids", group.agents)]

            per_agent_times = _compute_times_from_trajectory_sqlite(
                trajectory_db_file=trajectory_file,
                agent_ids=initial_agent_ids,
            )

            metrics = _compute_group_metrics(
                graph=G,
                group_path_df=group_path_df,
                agent_area_conn=agent_area_conn,
                group_id=group_id,
                agent_ids=initial_agent_ids,
                per_agent_times=per_agent_times,
            )

            log.info(
                "Metrics preview | mode=%s group=%s agents=%d min=%.3f avg=%.3f median=%.3f p90=%.3f max=%.3f",
                mode,
                group_id,
                len(initial_agent_ids),
                metrics["min_time"],
                metrics["avg_time"],
                metrics["median_time"],
                metrics["p90_time"],
                metrics["max_time"],
            )

            write_experiment_metrics(
                results_db_conn,
                experiment_id=experiment_id,
                case_name=case_name_mode,
                agent_group_id=str(group_id),
                algorithm=algorithm,
                awareness=awareness,
                n_records=metrics["n_records"],
                mean_remaining_path_risk=metrics["mean_remaining_path_risk"],
                remaining_path_risk_var=metrics["remaining_path_risk_var"],
                cumulative_risk_exposure=metrics["cumulative_risk_exposure"],
                avg_path_cost=metrics["avg_path_cost"],
                avg_time=metrics["avg_time"],
                median_time=metrics["median_time"],
                p90_time=metrics["p90_time"],
                min_time=metrics["min_time"],
                max_time=metrics["max_time"],
            )

        # Persist mode results before moving to the next one
        results_db_conn.commit()

        _generate_mode_visual_artifacts(
            trajectory_file=trajectory_file,
            walkable_area=walkable_area,
            waypoints=waypoints,
            target_nodes=targets,
            specific_areas=specific_areas,
            risk_db_file=risk_db_file,
            danger_frame=danger_visualization_frame,
            artifacts_dir=paths.artifacts_dir,
            env_name=env_name,
            mode=mode,
        )

        # Close per-mode DB connections
        agent_area_conn.close()
        group_path_conn_mode.close()

        log.info("Finished mode=%s", mode)

    # Ensure final results are written
    results_db_conn.commit()

    experiments_csv = paths.artifacts_dir / "experiments.csv"
    metrics_csv = paths.artifacts_dir / "experiment_metrics.csv"

    export_experiments_to_csv(str(results_db_file), str(experiments_csv))
    export_experiment_metrics_to_csv(str(results_db_file), str(metrics_csv))

    log.info("Exported CSV: %s", experiments_csv)
    log.info("Exported CSV: %s", metrics_csv)

    # Close shared DB connections
    paths_conn.close()
    risk_db_conn.close()
    results_db_conn.close()

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def run_from_yaml(
    *,
    project_root: Path,
    config_name: str,
    case_id: str,
    out_dir: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    project_root = project_root.resolve()

    paths = _prepare_paths(project_root, config_name, case_id, out_dir)
    _setup_run_logging(paths.run_dir, verbose=verbose)

    defaults_file = project_root / "configs" / "defaults.yaml"
    defaults = {}
    if defaults_file.exists():
        defaults = yaml.safe_load(defaults_file.read_text(encoding="utf-8")) or {}

    case_cfg = _load_case(paths.config_file, case_id)
    cfg = _deep_merge(defaults, case_cfg)

    log.info("project_root = %s", paths.project_root)
    log.info("config_file  = %s", paths.config_file)
    log.info("case_id      = %s", case_id)
    log.info("run_dir      = %s", paths.run_dir)

    (paths.run_dir / "config_resolved.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8",
    )

    metadata = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "case_id": case_id,
        "config_name": config_name,
        "environment": cfg.get("environment"),
        "git_commit": _git_commit_hash(paths.project_root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }

    (paths.run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    try:
        _run_experiment_from_case(cfg, paths, case_id)
    except Exception:
        log.exception("Experiment crashed (case_id=%s)", case_id)
        raise
    else:
        log.info("Experiment finished OK (case_id=%s)", case_id)
