from __future__ import annotations

import logging

import jupedsim as jps

from evac_sim.db.repositories.risk import get_risk_levels_by_frame
from evac_sim.simulation.group_processing import process_single_group
from evac_sim.simulation.group_splitting import (
    next_split_group_id,
    split_group_by_progress_threshold,
)
from evac_sim.simulation.group_state import (
    ctx,
    remaining_path_from_node,
    uses_static_reservations,
    uses_temporal_reservations,
)
from evac_sim.simulation.simulation_logic import (
    clear_group_static_reservation_state,
    compute_current_nodes,
    release_group_static_reservations,
)
from evac_sim.simulation.temporal_capacity import release_temporal_path_reservation

logger = logging.getLogger(__name__)


def _set_current_frame_on_graph(env_info, frame: int) -> None:
    graph = getattr(env_info, "graph", None)

    if graph is None:
        return

    graph_metadata = getattr(graph, "graph", None)

    if graph_metadata is None:
        return

    graph_metadata["current_frame"] = frame

def process_frame(
    sim_cfg,
    groups: dict,
    env_info,
    conn,
    *,
    case_name: str,
    mode: int,
    frame: int,
    threshold: float,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    congestion_reroute_epsilon: float = 0.1,
    group_split_threshold: int | None = None,
    no_path_policy: str = "raise",
) -> None:
    risks = get_risk_levels_by_frame(conn, case_name, frame)

    _set_current_frame_on_graph(env_info, frame)

    for original_group_id, original_group in list(groups.items()):
        try:
            group = groups.get(original_group_id)
            if group is None:
                continue

            compute_current_nodes(sim_cfg, group, frame)

            active_ids = {agent.id for agent in sim_cfg.simulation.agents()}

            group.agents = [
                agent_id
                for agent_id in group.agents
                if agent_id in active_ids
            ]

            group.current_nodes = {
                agent_id: node
                for agent_id, node in group.current_nodes.items()
                if agent_id in active_ids
            }

            if not group.agents:
                continue

            groups_to_process = [(original_group_id, group)]

            split_result = split_group_by_progress_threshold(
                group,
                threshold=group_split_threshold,
            )

            if split_result is not None:
                lead_group, lag_group = split_result
                lag_group_id = next_split_group_id(
                    groups,
                    original_group_id,
                    suffix="lag",
                )

                logger.info(
                    "Group split applied | %s | threshold=%s | lead_agents=%d "
                    "lag_agents=%d new_group=%s",
                    ctx(
                        frame=frame,
                        group_id=original_group_id,
                        agents=len(group.agents),
                    ),
                    group_split_threshold,
                    len(lead_group.agents),
                    len(lag_group.agents),
                    lag_group_id,
                )

                if uses_static_reservations(heuristic):
                    release_group_static_reservations(env_info, group)
                elif uses_temporal_reservations(heuristic):
                    release_temporal_path_reservation(
                        env_info.graph,
                        group_id=original_group_id,
                    )
                else:
                    clear_group_static_reservation_state(group)

                groups[original_group_id] = lead_group
                groups[lag_group_id] = lag_group

                groups_to_process = [
                    (original_group_id, lead_group),
                    (lag_group_id, lag_group),
                ]

            for group_id, aligned_group in groups_to_process:
                if not aligned_group.agents:
                    continue

                process_single_group(
                    sim_cfg,
                    env_info,
                    conn,
                    risks,
                    groups,
                    case_name=case_name,
                    mode=mode,
                    frame=frame,
                    threshold=threshold,
                    heuristic=heuristic,
                    beta=beta,
                    horizon_k=horizon_k,
                    congestion_reroute_epsilon=congestion_reroute_epsilon,
                    no_path_policy=no_path_policy,
                    group_id=group_id,
                    group=aligned_group,
                )

        except Exception:
            logger.exception(
                "Group processing failed | %s",
                ctx(
                    frame=frame,
                    group_id=original_group_id,
                    agents=len(getattr(original_group, "agents", []) or []),
                ),
            )
            raise


def run_agent_simulation(
    sim_cfg,
    log_every_frames: int,
    agent_groups: dict,
    env_info,
    conn,
    *,
    case_name: str,
    mode: int,
    threshold: float,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    congestion_reroute_epsilon: float = 0.1,
    group_split_threshold: int | None = None,
    no_path_policy: str = "raise",
) -> None:
    """
    Advance the simulation and periodically process agent movements and path updates.
    """
    sim = sim_cfg.simulation
    max_frames = 20000

    logger.info("Simulation start | agents=%d", sim.agent_count())

    if sim.agent_count() > 0:
        process_frame(
            sim_cfg,
            agent_groups,
            env_info,
            conn,
            case_name=case_name,
            mode=mode,
            frame=0,
            threshold=threshold,
            heuristic=heuristic,
            beta=beta,
            horizon_k=horizon_k,
            congestion_reroute_epsilon=congestion_reroute_epsilon,
            group_split_threshold=group_split_threshold,
            no_path_policy=no_path_policy,
        )

    last_log_frame = -1
    frame = 0

    while sim.agent_count() > 0:
        sim.iterate()
        iteration = sim.iteration_count()

        if iteration % sim_cfg.every_nth_frame_simulation != 0:
            continue

        frame = iteration // sim_cfg.every_nth_frame_simulation

        if frame > max_frames:
            logger.error(
                "Simulation stopped by max_frames | iteration=%d | remaining_agents=%d",
                iteration,
                sim.agent_count(),
            )
            break

        if frame % log_every_frames == 0 and frame != last_log_frame:
            last_log_frame = frame

            group_status = {}

            for group_id, group in agent_groups.items():
                if not group.agents:
                    continue

                agents_data = {}

                for agent_id in group.agents:
                    current_node = group.current_nodes.get(agent_id)

                    agents_data[agent_id] = {
                        "current_node": current_node,
                        "remaining_path_head": remaining_path_from_node(
                            group.path,
                            current_node,
                        )[:8],
                        "waiting_due_to_congestion": getattr(
                            group,
                            "waiting_due_to_congestion",
                            False,
                        ),
                    }

                group_status[str(group_id)] = {
                    "agents": len(group.agents),
                    "waiting_due_to_congestion": getattr(
                        group,
                        "waiting_due_to_congestion",
                        False,
                    ),
                    "agents_data": agents_data,
                }

            logger.info(
                "Progress | frame=%d | agents=%d | groups=%s",
                frame,
                sim.agent_count(),
                group_status,
            )

        if frame % sim_cfg.every_nth_frame_animation == 0:
            process_frame(
                sim_cfg,
                agent_groups,
                env_info,
                conn,
                case_name=case_name,
                mode=mode,
                frame=frame,
                threshold=threshold,
                heuristic=heuristic,
                beta=beta,
                horizon_k=horizon_k,
                congestion_reroute_epsilon=congestion_reroute_epsilon,
                group_split_threshold=group_split_threshold,
                no_path_policy=no_path_policy,
            )

    logger.info("Simulation end | last_frame=%d", frame)


def set_agents_in_simulation(
    simulation,
    positions: list,
    journey_id: int,
    waypoint_id: int,
    speed: float,
) -> list:
    """
    Add multiple agents to the simulation with the same journey and speed.

    Returns a list of new agent instances.
    """
    new_agents = []

    for position in positions:
        params = jps.CollisionFreeSpeedModelAgentParameters(
            position=position,
            journey_id=journey_id,
            stage_id=waypoint_id,
            desired_speed=speed,
        )
        new_agents.append(simulation.add_agent(params))

    return new_agents