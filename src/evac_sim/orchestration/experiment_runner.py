from __future__ import annotations

import gc
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jupedsim as jps
import numpy as np

from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.core.risk_simulation_values import RiskSimulationValues
from evac_sim.core.simulation_config import SimulationConfig

from evac_sim.db.agent_area_db_manager import (
    create_agent_area_table,
)
from evac_sim.db.danger_sim_db_manager import (
    create_risk_table,
    get_risk_levels_by_frame,
)
from evac_sim.db.group_path_db_manager import (
    create_group_path_table,
    read_group_path_data,
)
from evac_sim.db.paths_db_manager import create_paths_table
from evac_sim.db.simulation_results_db_manager import (
    create_tables,
    export_experiment_metrics_to_csv,
    export_experiments_to_csv,
    write_experiment,
    write_experiment_metrics,
)

import evac_sim.envs.environment as pol
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.risk.risk_simulation import simulate_risk
from evac_sim.routing.decision_policies import compute_alternative_path
from evac_sim.simulation.simulation_manager import (
    run_agent_simulation,
    set_agents_in_simulation,
)

from evac_sim.analysis.metrics import compute_group_metrics
from evac_sim.db.sqlite_utils import (
    compute_times_from_trajectory_sqlite,
    init_db_connection,
)
from evac_sim.envs.environment_factory import select_environment
from evac_sim.io.run_paths import RunPaths
from evac_sim.viz.plots import generate_mode_visual_artifacts

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class AgentPositioningConfig:
    distance_to_agents: float
    distance_to_polygon: float
    agent_position_seed: int


@dataclass(frozen=True)
class JuPedSimConfig:
    strength_neighbor_repulsion: float
    range_neighbor_repulsion: float
    range_geometry_repulsion: float

@dataclass(frozen=True)
class ExperimentResources:
    env_name: str
    walkable_area: Any
    obstacles: Any
    targets: list[Any]
    sources: list[Any]
    total_agents: list[int]
    waypoints: dict[Any, Any]
    graph: Any
    specific_areas: dict[Any, Any]
    env_info: EnvironmentInfo
    positions: dict[str, np.ndarray]
    risk_first_frame: dict[Any, float]
    risk_db_file: Path
    results_db_file: Path
    risk_db_conn: sqlite3.Connection
    paths_conn: sqlite3.Connection
    group_path_conn: sqlite3.Connection
    results_db_conn: sqlite3.Connection
    danger_visualization_frame: int | None
    risk_seed: int
    risk_threshold: float
    gamma: float
    stairs_max_speed: float
    normal_max_speed: float
    every_nth_frame_simulation: int
    every_nth_frame_animation: int
    mode_type: int
    modes: list[int]
    agent_positioning: AgentPositioningConfig
    jps_config: JuPedSimConfig


def build_modes(mode_type: int):
    mode_indices = {
        0: [0, 1, 2, 3],
        1: [0, 1],
        2: [0, 1],
        3: [2, 3],
        4: [2]
    }

    if mode_type not in mode_indices:
        raise ValueError(f"Unsupported mode_type: {mode_type}")
    return mode_indices[mode_type]

def allocate_positions(
        *,
        sources:list[Any],
        total_agents: list[int],
        specific_areas: dict[Any, Any],
        distance_to_agents: float,
        distance_to_polygon: float,
        seed: int

) -> dict[str, np.ndarray]:
    positions: dict[str, np.ndarray] = {}

    for i, source in enumerate(sources):
        positions[source] = jps.distribute_by_number(
            polygon=specific_areas[source],
            number_of_agents=total_agents[i],
            distance_to_agents=distance_to_agents,
            distance_to_polygon=distance_to_polygon,
            seed=seed,
        )

    return positions

def prepare_shared_resources(cfg: dict[str, Any], paths: RunPaths) -> ExperimentResources:
    env = select_environment(cfg["environment"])

    env_name = env.name
    walkable_area = env.walkable_area
    obstacles = env.obstacles
    targets = cfg["targets"]
    sources = cfg["sources"]
    total_agents = cfg["agents"]
    waypoints = env.waypoints
    graph = env.graph
    specific_areas = env.specific_areas

    mode_type = int(cfg.get("mode_type", 0))
    modes = build_modes(mode_type)

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

    danger_visualization_frame = cfg.get(
        "danger_visualization_frame",
        cfg.get("danger_frame", None),
    )
    if danger_visualization_frame is not None:
        danger_visualization_frame = int(danger_visualization_frame)

    starting_risks = [tuple(x) for x in (cfg.get("starting_risks", []) or [])]
    risk_overrides = [tuple(x) for x in (cfg.get("risk_overrides", []) or [])]

    risk_db_file = paths.artifacts_dir / f"{env_name}_risks.db"
    paths_db_file = paths.artifacts_dir / f"{env_name}_paths.db"
    group_paths_db_file = paths.artifacts_dir / f"{env_name}_group_paths.db"
    results_db_file = paths.artifacts_dir / f"{env_name}_results.db"

    risk_db_conn = init_db_connection(risk_db_file, create_risk_table)
    paths_conn = init_db_connection(paths_db_file, create_paths_table)
    group_path_conn = init_db_connection(group_paths_db_file, create_group_path_table)
    results_db_conn = init_db_connection(results_db_file, create_tables)

    pol.set_targets(targets, env)

    distance_to_agents = cfg.get("distance_to_agents", None)
    distance_to_polygon = cfg.get("distance_to_polygon", None)
    agent_position_seed = cfg.get("agent_position_seed", None)

    agent_positioning = AgentPositioningConfig(
        distance_to_agents=distance_to_agents,
        distance_to_polygon=distance_to_polygon,
        agent_position_seed=agent_position_seed,
    )

    positions = allocate_positions(
        sources=sources,
        total_agents=total_agents,
        specific_areas=specific_areas,
        distance_to_agents=agent_positioning.distance_to_agents,
        distance_to_polygon=agent_positioning.distance_to_polygon,
        seed=agent_positioning.agent_position_seed,
    )

    strength_neighbor_repulsion = cfg.get("strength_neighbor_repulsion", 0)
    range_neighbor_repulsion = cfg.get("range_neighbor_repulsion", 0)
    range_geometry_repulsion = cfg.get("range_geometry_repulsion", 0)

    jps_config = JuPedSimConfig(
        strength_neighbor_repulsion=strength_neighbor_repulsion,
        range_neighbor_repulsion=range_neighbor_repulsion,
        range_geometry_repulsion=range_geometry_repulsion,
    )

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
        graph,
        targets,
        risk_db_conn,
        risk_seed,
    )
    risk_first_frame = get_risk_levels_by_frame(risk_db_conn, 0)

    env_info = EnvironmentInfo(graph, paths_conn, floor_number=env.floor_number)
    if env.floor_number > 1:
        env_info.floors = env.floors
        env_info.floor_connecting_nodes = env.floor_connecting_nodes

    return ExperimentResources(
        env_name=env_name,
        walkable_area=walkable_area,
        obstacles=obstacles,
        targets=targets,
        sources=sources,
        total_agents=total_agents,
        waypoints=waypoints,
        graph=graph,
        specific_areas=specific_areas,
        env_info=env_info,
        positions=positions,
        risk_first_frame=risk_first_frame,
        risk_db_file=risk_db_file,
        results_db_file=results_db_file,
        risk_db_conn=risk_db_conn,
        paths_conn=paths_conn,
        group_path_conn=group_path_conn,
        results_db_conn=results_db_conn,
        danger_visualization_frame=danger_visualization_frame,
        risk_seed=risk_seed,
        risk_threshold=risk_threshold,
        gamma=gamma,
        stairs_max_speed=stairs_max_speed,
        normal_max_speed=normal_max_speed,
        every_nth_frame_simulation=every_nth_frame_simulation,
        every_nth_frame_animation=every_nth_frame_animation,
        mode_type=mode_type,
        modes=modes,
        agent_positioning=agent_positioning,
        jps_config=jps_config,
    )

def build_agent_groups(
    *,
    simulation: jps.Simulation,
    mode: int,
    mode_type: int,
    sources: list[Any],
    targets: list[Any],
    positions: dict[str, np.ndarray],
    waypoints: dict[Any, Any],
    exit_ids: dict[Any, Any],
    waypoints_ids: dict[Any, Any],
    env_info: EnvironmentInfo,
    risk_first_frame: dict[Any, float],
    gamma: float,
    normal_max_speed: float,
) -> dict[str, AgentGroup]:
    awareness_levels_per_group = [0, 1, 0, 1]
    algorithm_per_group = [0, 0, 1, 1]

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
        group.initial_agent_ids = list(agent_ids)

        agent_groups[source] = group

    return agent_groups

def create_simulation(
    *,
    walkable_area: Any,
    trajectory_file: Path,
    every_nth_frame_simulation: int,
    strength_neighbor_repulsion: float,
    range_neighbor_repulsion: float,
    range_geometry_repulsion: float,
) -> jps.Simulation:
    return jps.Simulation(
        model=jps.CollisionFreeSpeedModel(
            strength_neighbor_repulsion=strength_neighbor_repulsion,
            range_neighbor_repulsion=range_neighbor_repulsion,
            range_geometry_repulsion=range_geometry_repulsion,
        ),
        geometry=walkable_area.polygon,
        trajectory_writer=jps.SqliteTrajectoryWriter(
            output_file=Path(trajectory_file),
            every_nth_frame=every_nth_frame_simulation,
        ),
    )


def create_stages(
    *,
    simulation: jps.Simulation,
    targets: list[Any],
    specific_areas: dict[Any, Any],
    waypoints: dict[Any, Any],
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    exit_ids: dict[Any, Any] = {}
    for area_id in targets:
        exit_ids[area_id] = simulation.add_exit_stage(specific_areas[area_id])

    waypoints_ids: dict[Any, Any] = {}
    for node, (waypoint, distance) in waypoints.items():
        waypoints_ids[node] = simulation.add_waypoint_stage(waypoint, distance)

    return exit_ids, waypoints_ids

def write_mode_results(
    *,
    case_id: str,
    mode: int,
    graph: Any,
    results_db_conn: sqlite3.Connection,
    trajectory_file: Path,
    risk_seed: int,
    targets: list[Any],
    sources: list[Any],
    total_agents: list[int],
    group_path_conn_mode: sqlite3.Connection,
    agent_area_conn: sqlite3.Connection,
    agent_groups: dict[str, AgentGroup],
) -> None:
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

        initial_agent_ids = [
            int(a) for a in getattr(group, "initial_agent_ids", group.agents)
        ]

        per_agent_times = compute_times_from_trajectory_sqlite(
            trajectory_db_file=trajectory_file,
            agent_ids=initial_agent_ids,
        )

        metrics = compute_group_metrics(
            graph=graph,
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

def run_single_mode(
        *,
        cfg: dict[str, Any],
        case_id: str,
        mode: int,
        paths: RunPaths,
        resources: ExperimentResources,
) -> None:
    log.info(
        "Mode start | mode=%s env=%s case=%s",
        mode,
        resources.env_name,
        cfg.get("name", "unknown"),
    )

    trajectory_file = paths.artifacts_dir / f"{resources.env_name}_mode_{mode}.sqlite"

    simulation = create_simulation(
        walkable_area=resources.walkable_area,
        trajectory_file=trajectory_file,
        every_nth_frame_simulation=resources.every_nth_frame_simulation,
        strength_neighbor_repulsion=resources.jps_config.strength_neighbor_repulsion,
        range_neighbor_repulsion=resources.jps_config.range_neighbor_repulsion,
        range_geometry_repulsion=resources.jps_config.range_geometry_repulsion,
    )

    agent_area_db_file = paths.artifacts_dir / f"agent_area_{resources.env_name}_mode_{mode}.db"
    agent_area_conn = sqlite3.connect(str(agent_area_db_file))
    create_agent_area_table(agent_area_conn)

    group_paths_db_file_mode = (
            paths.artifacts_dir / f"{resources.env_name}_group_paths_mode_{mode}.db"
    )
    group_path_conn_mode = init_db_connection(
        group_paths_db_file_mode,
        create_group_path_table,
    )

    exit_ids, waypoints_ids = create_stages(
        simulation=simulation,
        targets=resources.targets,
        specific_areas=resources.specific_areas,
        waypoints=resources.waypoints,
    )

    agent_groups = build_agent_groups(
        simulation=simulation,
        mode=mode,
        mode_type=resources.mode_type,
        sources=resources.sources,
        targets=resources.targets,
        positions=resources.positions,
        waypoints=resources.waypoints,
        exit_ids=exit_ids,
        waypoints_ids=waypoints_ids,
        env_info=resources.env_info,
        risk_first_frame=resources.risk_first_frame,
        gamma=resources.gamma,
        normal_max_speed=resources.normal_max_speed,
    )

    sim_cfg = SimulationConfig(
        simulation,
        resources.every_nth_frame_simulation,
        resources.every_nth_frame_animation,
        waypoints_ids,
        exit_ids,
        resources.gamma,
        resources.normal_max_speed,
        resources.stairs_max_speed,
    )

    risk_db_conn_mode = sqlite3.connect(str(resources.risk_db_file))

    try:
        run_agent_simulation(
            sim_cfg,
            cfg.get("log_every_frames", 10),
            agent_groups,
            resources.env_info,
            risk_db_conn_mode,
            agent_area_conn,
            group_path_conn_mode,
            threshold=resources.risk_threshold,
        )
    except Exception:
        log.exception("Simulation failed | mode=%s", mode)
        raise
    finally:
        risk_db_conn_mode.close()

    del sim_cfg
    del simulation
    gc.collect()

    write_mode_results(
        case_id=case_id,
        mode=mode,
        graph=resources.graph,
        results_db_conn=resources.results_db_conn,
        trajectory_file=trajectory_file,
        risk_seed=resources.risk_seed,
        targets=resources.targets,
        sources=resources.sources,
        total_agents=resources.total_agents,
        group_path_conn_mode=group_path_conn_mode,
        agent_area_conn=agent_area_conn,
        agent_groups=agent_groups,
    )

    resources.results_db_conn.commit()

    generate_mode_visual_artifacts(
        trajectory_file=trajectory_file,
        walkable_area=resources.walkable_area,
        waypoints=resources.waypoints,
        target_nodes=resources.targets,
        specific_areas=resources.specific_areas,
        risk_db_file=resources.risk_db_file,
        danger_frame=resources.danger_visualization_frame,
        artifacts_dir=paths.artifacts_dir,
        env_name=resources.env_name,
        mode=mode,
    )

    agent_area_conn.close()
    group_path_conn_mode.close()

    log.info("Finished mode=%s", mode)

def export_final_results(
    *,
    results_db_file: Path,
    artifacts_dir: Path,
) -> None:
    experiments_csv = artifacts_dir / "experiments.csv"
    metrics_csv = artifacts_dir / "experiment_metrics.csv"

    export_experiments_to_csv(str(results_db_file), str(experiments_csv))
    export_experiment_metrics_to_csv(str(results_db_file), str(metrics_csv))

    log.info("Exported CSV: %s", experiments_csv)
    log.info("Exported CSV: %s", metrics_csv)


def run_experiment_from_case(
    cfg: dict[str, Any],
    paths: RunPaths,
    case_id: str,
) -> None:
    resources = prepare_shared_resources(cfg, paths)

    try:
        for mode in resources.modes:
            run_single_mode(
                cfg=cfg,
                case_id=case_id,
                mode=mode,
                paths=paths,
                resources=resources,
            )

        resources.results_db_conn.commit()

        export_final_results(
            results_db_file=resources.results_db_file,
            artifacts_dir=paths.artifacts_dir,
        )
    finally:
        resources.paths_conn.close()
        resources.risk_db_conn.close()
        resources.group_path_conn.close()
        resources.results_db_conn.close()