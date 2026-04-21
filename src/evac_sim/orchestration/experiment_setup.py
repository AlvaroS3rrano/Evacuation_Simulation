from __future__ import annotations

import random
import sqlite3
from pathlib import Path
from typing import Any

import jupedsim as jps
import numpy as np

import evac_sim.envs.environment as pol
from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.core.risk_simulation_values import RiskSimulationValues
from evac_sim.db.repositories.risk import get_risk_levels_by_frame
from evac_sim.db.schema import create_simulation_tables
from evac_sim.db.sqlite_utils import init_db_connection
from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.io.run_paths import RunPaths
from evac_sim.risk.risk_simulation import simulate_risk
from evac_sim.risk.risk_validation import validate_risk_inputs
from evac_sim.routing.decision_policies import compute_initial_path
from evac_sim.simulation.simulation_logic import update_group_reserved_edges
from evac_sim.simulation.simulation_manager import set_agents_in_simulation

from evac_sim.orchestration.experiment_models import (
    AgentPositioningConfig,
    ExperimentResources,
    JuPedSimConfig,
)


def _uses_reservations(heuristic: str) -> bool:
    return heuristic != "none"


def _initial_reservation_horizon(
    heuristic: str,
    horizon_k: int | None,
) -> int | None:
    if heuristic == "h2":
        return horizon_k
    return None


def _build_random_seeds(cfg: dict[str, Any]) -> tuple[int, int]:
    master_seed = cfg.get("master_seed", 42)
    master_rng = random.Random(master_seed)
    risk_seed = master_rng.randint(0, 2**32 - 1)
    agent_seed = master_rng.randint(0, 2**32 - 1)
    return risk_seed, agent_seed


def _resolve_simulation_connection(
    *,
    paths: RunPaths,
    shared_simulation_conn: sqlite3.Connection | None,
    shared_simulation_db_file: Path | None,
) -> tuple[sqlite3.Connection, Path, bool]:
    if shared_simulation_conn is not None:
        if shared_simulation_db_file is None:
            raise ValueError(
                "shared_simulation_db_file must be provided with shared_simulation_conn"
            )
        return shared_simulation_conn, shared_simulation_db_file, False

    simulation_db_file = paths.db_dir / "simulation.db"
    simulation_conn = init_db_connection(
        simulation_db_file,
        create_simulation_tables,
    )
    return simulation_conn, simulation_db_file, True


def _build_agent_positioning_config(
    cfg: dict[str, Any],
    agent_seed: int,
) -> AgentPositioningConfig:
    return AgentPositioningConfig(
        distance_to_agents=cfg.get("distance_to_agents", None),
        distance_to_polygon=cfg.get("distance_to_polygon", None),
        agent_position_seed=agent_seed,
    )


def _build_jps_config(cfg: dict[str, Any]) -> JuPedSimConfig:
    return JuPedSimConfig(
        strength_neighbor_repulsion=cfg.get("strength_neighbor_repulsion", 0),
        range_neighbor_repulsion=cfg.get("range_neighbor_repulsion", 0),
        range_geometry_repulsion=cfg.get("range_geometry_repulsion", 0),
    )


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


def _prepare_risk_state(
    *,
    cfg: dict[str, Any],
    risk_graph,
    targets: list[Any],
    simulation_conn: sqlite3.Connection,
    case_name: str,
    risk_seed: int,
    every_nth_frame_animation: int,
) -> dict[Any, float]:
    risk_iterations = int(cfg["risk_iterations"])
    risk_increase_chance = float(cfg["risk_increase_chance"])
    propagation_threshold = float(cfg["propagation_threshold"])
    risk_threshold = float(cfg["risk_threshold"])

    starting_risks = [
        (str(node_id), float(risk))
        for node_id, risk in (cfg.get("starting_risks", []) or [])
    ]

    risk_overrides = [
        (int(frame), str(node_id), float(risk))
        for frame, node_id, risk in (cfg.get("risk_overrides", []) or [])
    ]

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

    simulate_risk(
        risk_values,
        every_nth_frame_animation,
        risk_graph,
        targets,
        simulation_conn,
        risk_seed,
        case_name=case_name,
    )

    return get_risk_levels_by_frame(simulation_conn, case_name, 0)


def prepare_shared_resources(
    cfg: dict[str, Any],
    paths: RunPaths,
    case_name: str,
    shared_simulation_conn: sqlite3.Connection | None = None,
    shared_simulation_db_file: Path | None = None,
) -> ExperimentResources:
    env = select_environment(cfg["environment"])

    graph = env.graph.copy()
    risk_graph = graph.copy()

    targets = cfg["targets"]
    sources = cfg["sources"]
    total_agents = cfg["agents"]

    mode_type = int(cfg.get("mode_type", 0))
    modes = build_modes(mode_type)

    risk_seed, agent_seed = _build_random_seeds(cfg)

    simulation_conn, simulation_db_file, owns_simulation_conn = (
        _resolve_simulation_connection(
            paths=paths,
            shared_simulation_conn=shared_simulation_conn,
            shared_simulation_db_file=shared_simulation_db_file,
        )
    )

    pol.set_targets(targets, env)

    agent_positioning = _build_agent_positioning_config(cfg, agent_seed)
    positions = allocate_positions(
        sources=sources,
        total_agents=total_agents,
        specific_areas=env.specific_areas,
        distance_to_agents=agent_positioning.distance_to_agents,
        distance_to_polygon=agent_positioning.distance_to_polygon,
        seed=agent_positioning.agent_position_seed,
    )

    jps_config = _build_jps_config(cfg)

    every_nth_frame_simulation = int(cfg["every_nth_frame_simulation"])
    every_nth_frame_animation = int(cfg["every_nth_frame_animation"])

    risk_first_frame = _prepare_risk_state(
        cfg=cfg,
        risk_graph=risk_graph,
        targets=targets,
        simulation_conn=simulation_conn,
        case_name=case_name,
        risk_seed=risk_seed,
        every_nth_frame_animation=every_nth_frame_animation,
    )

    env_info = EnvironmentInfo(graph, simulation_conn, floor_number=env.floor_number)
    if env.floor_number > 1:
        env_info.floors = env.floors
        env_info.floor_connecting_nodes = env.floor_connecting_nodes

    danger_visualization_frame = cfg.get(
        "danger_visualization_frame",
        cfg.get("danger_frame", None),
    )
    if danger_visualization_frame is not None:
        danger_visualization_frame = int(danger_visualization_frame)

    return ExperimentResources(
        env_name=env.name,
        walkable_area=env.walkable_area,
        obstacles=env.obstacles,
        targets=targets,
        sources=sources,
        total_agents=total_agents,
        waypoints=env.waypoints,
        graph=graph,
        specific_areas=env.specific_areas,
        env_info=env_info,
        positions=positions,
        risk_first_frame=risk_first_frame,
        simulation_db_file=simulation_db_file,
        simulation_conn=simulation_conn,
        danger_visualization_frame=danger_visualization_frame,
        risk_seed=risk_seed,
        risk_threshold=float(cfg["risk_threshold"]),
        gamma=float(cfg["gamma"]),
        stairs_max_speed=float(cfg["stairs_max_speed"]),
        normal_max_speed=float(cfg["normal_max_speed"]),
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

    return sum(env_info.graph[u][v]["cost"] for u, v in zip(path, path[1:]))


def _resolve_group_strategy(
    mode: int,
    mode_type: int,
    source_index: int,
) -> tuple[int, int]:
    awareness_levels_per_group = [0, 1, 0, 1]
    algorithm_per_group = [0, 0, 1, 1]

    if mode_type == 1:
        return source_index, mode

    return algorithm_per_group[mode], awareness_levels_per_group[mode]


def _build_group_candidates(
    *,
    mode: int,
    mode_type: int,
    sources: list[Any],
    positions: dict[str, np.ndarray],
    targets: list[Any],
    env_info: EnvironmentInfo,
    gamma: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for i, source in enumerate(sources):
        algorithm, awareness_level = _resolve_group_strategy(mode, mode_type, i)
        group_size = len(positions[source])

        base_exit_cost = compute_initial_priority_cost(
            source=source,
            targets=targets,
            env_info=env_info,
            algorithm=algorithm,
            gamma=gamma,
        )

        candidates.append(
            {
                "source": source,
                "group_size": group_size,
                "algorithm": algorithm,
                "awareness_level": awareness_level,
                "base_exit_cost": base_exit_cost,
            }
        )

    candidates.sort(
        key=lambda g: (g["base_exit_cost"], -g["group_size"], str(g["source"]))
    )
    return candidates


def _create_initial_group(
    *,
    simulation: jps.Simulation,
    source: Any,
    group_size: int,
    algorithm: int,
    awareness_level: int,
    targets: list[Any],
    positions: dict[str, np.ndarray],
    waypoints_ids: dict[Any, Any],
    exit_ids: dict[Any, Any],
    env_info: EnvironmentInfo,
    risk_first_frame: dict[Any, float],
    gamma: float,
    normal_max_speed: float,
    heuristic: str,
    beta: float,
    horizon_k: int | None,
) -> AgentGroup:
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

    if path is None:
        raise ValueError(f"No initial path found for source={source}")

    if not isinstance(path, (list, tuple)) or len(path) < 2:
        raise ValueError(f"Invalid initial path for source={source}: {path}")

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

    if _uses_reservations(heuristic):
        update_group_reserved_edges(
            env_info,
            group,
            frame=0,
            group_id=source,
            horizon_k=_initial_reservation_horizon(heuristic, horizon_k),
        )

    return group


def build_agent_groups(
    *,
    simulation: jps.Simulation,
    mode: int,
    mode_type: int,
    sources: list[Any],
    targets: list[Any],
    positions: dict[str, np.ndarray],
    exit_ids: dict[Any, Any],
    waypoints_ids: dict[Any, Any],
    env_info: EnvironmentInfo,
    risk_first_frame: dict[Any, float],
    gamma: float,
    normal_max_speed: float,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    logger=None,
) -> dict[str, AgentGroup]:
    agent_groups: dict[str, AgentGroup] = {}

    group_candidates = _build_group_candidates(
        mode=mode,
        mode_type=mode_type,
        sources=sources,
        positions=positions,
        targets=targets,
        env_info=env_info,
        gamma=gamma,
    )

    if logger is not None:
        logger.info(
            "Initial assignment order: %s",
            [
                (g["source"], g["group_size"], round(g["base_exit_cost"], 3))
                for g in group_candidates
            ],
        )

    for group_info in group_candidates:
        source = group_info["source"]

        group = _create_initial_group(
            simulation=simulation,
            source=source,
            group_size=group_info["group_size"],
            algorithm=group_info["algorithm"],
            awareness_level=group_info["awareness_level"],
            targets=targets,
            positions=positions,
            waypoints_ids=waypoints_ids,
            exit_ids=exit_ids,
            env_info=env_info,
            risk_first_frame=risk_first_frame,
            gamma=gamma,
            normal_max_speed=normal_max_speed,
            heuristic=heuristic,
            beta=beta,
            horizon_k=horizon_k,
        )

        agent_groups[source] = group

        if logger is not None:
            logger.info(
                "Initial group created | source=%s agents=%d path=%s reserved_edges=%d",
                source,
                len(group.agents),
                group.path,
                len(group.reserved_edges),
            )

    return agent_groups