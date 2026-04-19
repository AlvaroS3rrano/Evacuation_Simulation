from __future__ import annotations

import gc
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import random

import jupedsim as jps
import numpy as np

from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.core.risk_simulation_values import RiskSimulationValues
from evac_sim.core.simulation_config import SimulationConfig

from evac_sim.db.schema import create_simulation_tables
from evac_sim.db.repositories.risk import get_risk_levels_by_frame
from evac_sim.db.repositories.group_decisions import get_group_decisions_dataframe
from evac_sim.db.repositories.experiments import (
    upsert_experiment,
    upsert_experiment_metrics,
    ExperimentMetrics,
    ExperimentConfig,
)
from evac_sim.db.exporters.experiments_csv import (
    export_experiment_metrics_to_csv,
    export_experiments_to_csv,
)

import evac_sim.envs.environment as pol
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.risk.risk_simulation import simulate_risk
from evac_sim.risk.risk_validation import validate_risk_inputs
from evac_sim.routing.decision_policies import compute_initial_path
from evac_sim.simulation.simulation_manager import (
    run_agent_simulation,
    set_agents_in_simulation,
)
from evac_sim.simulation.simulation_logic import update_group_reserved_edges

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
    simulation_db_file: Path
    simulation_conn: sqlite3.Connection
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
    owns_simulation_conn: bool


def build_modes(mode_type: int) -> list[int]:
    mode_indices = {
        0: [0, 1, 2, 3],
        1: [0, 1],
        2: [0, 1],
        3: [2, 3],
        4: [2],
    }

    if mode_type not in mode_indices:
        raise ValueError(f"Unsupported mode_type: {mode_type}")
    return mode_indices[mode_type]


def allocate_positions(
    *,
    sources: list[Any],
    total_agents: list[int],
    specific_areas: dict[Any, Any],
    distance_to_agents: float,
    distance_to_polygon: float,
    seed: int,
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


def prepare_shared_resources(
    cfg: dict[str, Any],
    paths: RunPaths,
    case_name: str,
    shared_simulation_conn: sqlite3.Connection | None = None,
    shared_simulation_db_file: Path | None = None,
) -> ExperimentResources:
    env = select_environment(cfg["environment"])

    env_name = env.name
    walkable_area = env.walkable_area
    obstacles = env.obstacles
    targets = cfg["targets"]
    sources = cfg["sources"]
    total_agents = cfg["agents"]
    waypoints = env.waypoints
    graph = env.graph.copy()
    risk_graph = graph.copy()
    specific_areas = env.specific_areas

    mode_type = int(cfg.get("mode_type", 0))
    modes = build_modes(mode_type)

    master_seed = cfg.get("master_seed", 42)

    master_rng = random.Random(master_seed)

    risk_seed = master_rng.randint(0, 2 ** 32 - 1)
    agent_seed = master_rng.randint(0, 2 ** 32 - 1)

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

    starting_risks_raw = cfg.get("starting_risks", []) or []
    risk_overrides_raw = cfg.get("risk_overrides", []) or []

    starting_risks = [
        (str(node_id), float(risk))
        for node_id, risk in starting_risks_raw
    ]

    risk_overrides = [
        (int(frame), str(node_id), float(risk))
        for frame, node_id, risk in risk_overrides_raw
    ]

    if shared_simulation_conn is not None:
        simulation_conn = shared_simulation_conn
        if shared_simulation_db_file is None:
            raise ValueError(
                "shared_simulation_db_file must be provided with shared_simulation_conn"
            )
        simulation_db_file = shared_simulation_db_file
    else:
        simulation_db_file = paths.db_dir / "simulation.db"
        simulation_conn = init_db_connection(
            simulation_db_file,
            create_simulation_tables,
        )

    owns_simulation_conn = shared_simulation_conn is None

    pol.set_targets(targets, env)

    distance_to_agents = cfg.get("distance_to_agents", None)
    distance_to_polygon = cfg.get("distance_to_polygon", None)

    agent_positioning = AgentPositioningConfig(
        distance_to_agents=distance_to_agents,
        distance_to_polygon=distance_to_polygon,
        agent_position_seed=agent_seed,
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

    validate_risk_inputs(
        graph=risk_graph,
        exits=targets,
        risk_iterations=risk_iterations,
        every_nth_frame=every_nth_frame_animation,
        increase_chance=risk_increase_chance,
        propagation_threshold=propagation_threshold,
        risk_threshold=risk_threshold,
        starting_risks=starting_risks,
        risk_overrides=risk_overrides,
    )

    log.info("Simulating risks: iterations=%s seed=%s", risk_iterations, risk_seed)
    simulate_risk(
        risk_values,
        every_nth_frame_animation,
        risk_graph,
        targets,
        simulation_conn,
        risk_seed,
        case_name=case_name,
    )
    risk_first_frame = get_risk_levels_by_frame(simulation_conn, case_name, 0)

    env_info = EnvironmentInfo(graph, simulation_conn, floor_number=env.floor_number)
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
        simulation_db_file=simulation_db_file,
        simulation_conn=simulation_conn,
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
        owns_simulation_conn=owns_simulation_conn,
    )

def compute_initial_priority_cost(
    *,
    source: Any,
    targets: list[Any],
    env_info: EnvironmentInfo,
    algorithm: int,
    gamma: float,
) -> float:
    dummy_group = AgentGroup(
        agents=[],
        path=None,
        current_nodes={},
        algorithm=algorithm,
        awareness_level=0,
    )

    path = compute_initial_path(
        targets,
        dummy_group,
        env_info,
        source,
        risk_per_node=None,
        gamma=gamma,
        heuristic="none",
        beta=1.0,
        group_size=1,
    )

    if path is None or len(path) < 2:
        return float("inf")

    total_cost = 0.0
    for u, v in zip(path, path[1:]):
        total_cost += env_info.graph[u][v]["cost"]

    return total_cost

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
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
) -> dict[str, AgentGroup]:
    awareness_levels_per_group = [0, 1, 0, 1]
    algorithm_per_group = [0, 0, 1, 1]

    agent_groups: dict[str, AgentGroup] = {}

    # 1) Build candidate group metadata
    group_candidates = []

    for i, source in enumerate(sources):
        if mode_type == 1:
            algorithm = i
            awareness_level = mode
        else:
            algorithm = algorithm_per_group[mode]
            awareness_level = awareness_levels_per_group[mode]

        group_size = len(positions[source])

        base_exit_cost = compute_initial_priority_cost(
            source=source,
            targets=targets,
            env_info=env_info,
            algorithm=algorithm,
            gamma=gamma,
        )

        group_candidates.append(
            {
                "source": source,
                "group_size": group_size,
                "algorithm": algorithm,
                "awareness_level": awareness_level,
                "base_exit_cost": base_exit_cost,
            }
        )

    # 2) Order groups: closest first, then larger groups, then stable source id
    group_candidates.sort(
        key=lambda g: (g["base_exit_cost"], -g["group_size"], str(g["source"]))
    )

    log.info(
        "Initial assignment order: %s",
        [
            (g["source"], g["group_size"], round(g["base_exit_cost"], 3))
            for g in group_candidates
        ],
    )

    log.info(
        "Initial group ordering (closest_first): %s",
        [
            {
                "source": g["source"],
                "group_size": g["group_size"],
                "priority_cost": round(g["base_exit_cost"], 3),
            }
            for g in group_candidates
        ],
    )

    # 3) Assign paths sequentially and reserve immediately
    for group_info in group_candidates:
        source = group_info["source"]
        group_size = group_info["group_size"]
        algorithm = group_info["algorithm"]
        awareness_level = group_info["awareness_level"]

        group = AgentGroup(
            agents=[],
            path=None,
            current_nodes={},
            algorithm=algorithm,
            awareness_level=awareness_level,
        )

        path = compute_initial_path(
            targets,
            group,
            env_info,
            source,
            risk_per_node=risk_first_frame,
            gamma=gamma,
            heuristic=heuristic,
            beta=beta,
            group_size=group_size,
        )

        log.warning(
            "Initial path for source=%s size=%d priority_cost=%.3f -> %s",
            source,
            group_size,
            group_info["base_exit_cost"],
            path,
        )

        if path is None:
            raise ValueError(
                f"No initial path found for source={source} in mode={mode}"
            )

        if not isinstance(path, (list, tuple)) or len(path) < 2:
            raise ValueError(
                f"Invalid initial path for source={source}: {path}"
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
        group.initial_agents_ids = list(agent_ids)
        group.reserved_edges = set()
        group.reserved_group_size = 0

        reservation_horizon = None if heuristic=="h1" else horizon_k if heuristic=="h2" else None
        update_group_reserved_edges(
            env_info,
            group,
            frame=0,
            group_id=source,
            horizon_k=reservation_horizon,
        )

        agent_groups[source] = group

        log.info(
            "Initial reservation applied | source=%s agents=%d reserved_edges=%d",
            source,
            len(group.agents),
            len(group.reserved_edges),
        )

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
    simulation_conn: sqlite3.Connection,
    trajectory_file: Path,
    risk_seed: int,
    targets: list[Any],
    sources: list[Any],
    total_agents: list[int],
    agent_groups: dict[str, AgentGroup],
) -> None:
    case_name_mode = f"{case_id}_mode_{mode}"

    experiment = ExperimentConfig(
        case_name=case_name_mode,
        risk_nodes=targets,
        source_nodes=sources,
        agents_per_source=total_agents,
        random_seed=risk_seed,
    )

    experiment_id = upsert_experiment(
        simulation_conn,
        experiment,
    )

    group_path_df = get_group_decisions_dataframe(
        simulation_conn,
        case_id,
        mode,
    )

    for group_id, group in agent_groups.items():
        algorithm = "Centrality" if getattr(group, "algorithm", 0) == 1 else "Efficient"
        awareness = float(getattr(group, "awareness_level", 0))

        initial_agents_ids = [
            int(a) for a in getattr(group, "initial_agents_ids", group.agents)
        ]

        per_agent_times = compute_times_from_trajectory_sqlite(
            trajectory_db_file=trajectory_file,
            agent_ids=initial_agents_ids,
        )

        metrics = compute_group_metrics(
            graph=graph,
            group_path_df=group_path_df,
            agent_area_conn=simulation_conn,
            case_name=case_id,
            mode=mode,
            group_id=group_id,
            agent_ids=initial_agents_ids,
            per_agent_times=per_agent_times,
        )

        log.info(
            "Metrics preview | mode=%s group=%s agents=%d min=%.3f avg=%.3f median=%.3f p90=%.3f max=%.3f",
            mode,
            group_id,
            len(initial_agents_ids),
            metrics["min_time"],
            metrics["avg_time"],
            metrics["median_time"],
            metrics["p90_time"],
            metrics["max_time"],
        )

        experiment_metrics = ExperimentMetrics(
            experiment_id=experiment_id,
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

        upsert_experiment_metrics(
            simulation_conn,
            experiment_metrics,
        )


def run_single_mode(
    *,
    cfg: dict[str, Any],
    case_id: str,
    mode: int,
    paths: RunPaths,
    resources: ExperimentResources,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
) -> None:
    log.info(
        "Mode start | mode=%s env=%s case=%s",
        mode,
        resources.env_name,
        cfg.get("name", "unknown"),
    )

    trajectory_file = paths.db_dir / f"{resources.env_name}_mode_{mode}.sqlite"

    simulation = create_simulation(
        walkable_area=resources.walkable_area,
        trajectory_file=trajectory_file,
        every_nth_frame_simulation=resources.every_nth_frame_simulation,
        strength_neighbor_repulsion=resources.jps_config.strength_neighbor_repulsion,
        range_neighbor_repulsion=resources.jps_config.range_neighbor_repulsion,
        range_geometry_repulsion=resources.jps_config.range_geometry_repulsion,
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
        heuristic=heuristic,
        beta=beta,
        horizon_k=horizon_k,
    )

    sim_cfg = SimulationConfig(
        simulation=simulation,
        every_nth_frame_simulation=resources.every_nth_frame_simulation,
        every_nth_frame_animation=resources.every_nth_frame_animation,
        waypoints_ids=waypoints_ids,
        exit_ids=exit_ids,
        gamma=resources.gamma,
        normal_max_speed=resources.normal_max_speed,
        stairs_max_speed=resources.stairs_max_speed,
    )

    try:
        run_agent_simulation(
            sim_cfg,
            cfg.get("log_every_frames", 10),
            agent_groups,
            resources.env_info,
            resources.simulation_conn,
            case_name=case_id,
            mode=mode,
            threshold=resources.risk_threshold,
            heuristic=heuristic,
            beta=beta,
            horizon_k=horizon_k,
        )
    except Exception:
        log.exception("Simulation failed | mode=%s", mode)
        raise

    del sim_cfg
    del simulation
    gc.collect()

    write_mode_results(
        case_id=case_id,
        mode=mode,
        graph=resources.graph,
        simulation_conn=resources.simulation_conn,
        trajectory_file=trajectory_file,
        risk_seed=resources.risk_seed,
        targets=resources.targets,
        sources=resources.sources,
        total_agents=resources.total_agents,
        agent_groups=agent_groups,
    )

    resources.simulation_conn.commit()

    generate_mode_visual_artifacts(
        trajectory_file=trajectory_file,
        walkable_area=resources.walkable_area,
        waypoints=resources.waypoints,
        target_nodes=resources.targets,
        specific_areas=resources.specific_areas,
        risk_db_file=resources.simulation_db_file,
        case_name=case_id,
        danger_frame=resources.danger_visualization_frame,
        images_dir=paths.images_dir,
        env_name=resources.env_name,
        mode=mode,
    )

    log.info("Finished mode=%s", mode)


def export_final_results(
    *,
    simulation_db_file: Path,
    csv_dir: Path,
) -> None:
    experiments_csv = csv_dir / "experiments.csv"
    metrics_csv = csv_dir / "experiment_metrics.csv"

    export_experiments_to_csv(str(simulation_db_file), str(experiments_csv))
    export_experiment_metrics_to_csv(str(simulation_db_file), str(metrics_csv))

    log.info("Exported CSV: %s", experiments_csv)
    log.info("Exported CSV: %s", metrics_csv)


def run_experiment_from_case(
    cfg: dict[str, Any],
    paths: RunPaths,
    case_id: str,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    shared_simulation_conn: sqlite3.Connection | None = None,
    shared_simulation_db_file: Path | None = None,
) -> None:
    resources = prepare_shared_resources(
        cfg,
        paths,
        case_id,
        shared_simulation_conn,
        shared_simulation_db_file,
    )

    try:
        for mode in resources.modes:
            run_single_mode(
                cfg=cfg,
                case_id=case_id,
                mode=mode,
                paths=paths,
                resources=resources,
                heuristic=heuristic,
                beta=beta,
                horizon_k=horizon_k
            )

        resources.simulation_conn.commit()

        if resources.owns_simulation_conn:
            export_final_results(
                simulation_db_file=resources.simulation_db_file,
                csv_dir=paths.csv_dir,
            )
    finally:
        if resources.owns_simulation_conn:
            resources.simulation_conn.close()