from __future__ import annotations

import logging
from statistics import mean, pvariance

import jupedsim as jps

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.agent_area import insert_agent_areas
from evac_sim.db.repositories.risk import get_risk_levels_by_frame
from evac_sim.db.repositories.group_decisions import insert_group_decision
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.routing.decision_policies import compute_alternative_path
from evac_sim.routing.utils import is_sublist
from evac_sim.simulation.simulation_logic import compute_current_nodes, update_agent_speed_on_stairs, update_group_reserved_edges

logger = logging.getLogger(__name__)


def _ctx(
    *, frame: int | None = None, group_id: int | None = None, agents: int | None = None
) -> str:
    """Build a consistent context string for logs."""
    parts: list[str] = []
    if frame is not None:
        parts.append(f"frame={frame}")
    if group_id is not None:
        parts.append(f"group={group_id}")
    if agents is not None:
        parts.append(f"agents={agents}")
    return " | ".join(parts)

def _reservation_horizon_for_heuristic(heuristic: str, horizon_k: int | None):
    if heuristic == "h1":
        return None
    if heuristic == "h2":
        return horizon_k if horizon_k is not None else 3
    return None

def validate_agent(agent_id: int, simulation, current_nodes: dict) -> bool:
    """
    Check if an agent exists in the simulation and has a recorded current node.
    Returns True if valid, False otherwise.
    """
    exists = any(agent.id == agent_id for agent in simulation.agents())
    has_node = agent_id in current_nodes
    return exists and has_node


def try_get_node_index(node, path: list) -> int:
    """
    Attempt to find the index of a node in a path list.
    Returns the index or -1 if not found.
    """
    try:
        return path.index(node)
    except ValueError:
        return -1


def update_group_paths(
    sim_cfg,
    risk_map: dict,
    group: AgentGroup,
    env_info,
    threshold: float = 0.5,
    *,
    frame: int,
    group_id: int,
    heuristic: str = "none",
    beta: float = 1.0,
) -> AgentGroup:
    """
    Evaluates whether the group's path should be rerouted.
    If a better path is found, all agents follow the new path,
    and each is switched to the appropriate stage based on their current position.
    """
    agent_ids = group.agents
    if not agent_ids:
        return group

    current_path = group.path
    current_nodes = group.current_nodes
    simulation = sim_cfg.simulation
    waypoints = sim_cfg.waypoints_ids

    # Select the leading agent in the group (furthest along current_path)
    to_check = [max(agent_ids, key=lambda aid: current_path.index(current_nodes[aid]))]

    for aid in to_check:
        if not validate_agent(aid, simulation, current_nodes):
            return group

        curr_node = current_nodes[aid]
        idx = try_get_node_index(curr_node, current_path)
        if idx < 0 or idx >= len(current_path) - 1:
            continue

        next_node = current_path[idx + 1]

        # Compute an alternative path from the current node
        alt_path = compute_alternative_path(
            sim_cfg.exit_names,
            group,
            env_info,
            curr_node,
            next_node,
            risk_map,
            threshold,
            sim_cfg.gamma,
            heuristic=heuristic,
            beta=beta,
        )

        if alt_path and not is_sublist(alt_path, current_path):
            # Combine current_path up to curr_node with alt_path (avoid repeating curr_node)
            try:
                current_idx = current_path.index(curr_node)
                full_path = current_path[: current_idx + 1] + alt_path[1:]
            except ValueError:
                full_path = alt_path  # fallback

            # Create a new journey using the full_path
            journeys = set_journeys(
                simulation,
                curr_node,
                [full_path],
                waypoints,
                sim_cfg.exit_ids,
            )
            new_jid, _ = journeys[curr_node][0]

            # Assign each agent to the correct stage along the new path
            for agent_id in agent_ids:
                node = current_nodes[agent_id]
                try:
                    node_idx = full_path.index(node)
                    next_stage_node = full_path[min(node_idx + 1, len(full_path) - 1)]
                except ValueError:
                    next_stage_node = full_path[1] if len(full_path) > 1 else full_path[0]

                stage_id = waypoints[next_stage_node]
                simulation.switch_agent_journey(agent_id, new_jid, stage_id)

            logger.info(
                "Reroute applied | %s | curr=%s next=%s | old_len=%d new_len=%d",
                _ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                curr_node,
                next_node,
                len(current_path),
                len(full_path),
            )

            group.path = full_path
            return group

    return group


def record_group_path_data(
    connection,
    *,
    case_name: str,
    mode: int,
    frame: int,
    group_id: str,
    group: AgentGroup,
    risks: dict,
) -> None:
    algorithm = "Centrality" if group.algorithm == 1 else "Efficient"
    awareness = "High" if group.awareness_level == 1 else "Low"

    max_idx = -1
    current_area = None
    for aid in group.agents:
        area = group.current_nodes.get(aid)
        if area is None:
            continue
        try:
            idx = group.path.index(area)
        except ValueError:
            idx = -1
        if idx > max_idx:
            max_idx = idx
            current_area = area

    if current_area is None and group.agents:
        current_area = group.current_nodes.get(group.agents[0])

    next_path = group.path[max_idx:] if max_idx >= 0 else group.path
    risk_values = [risks.get(area, 0.0) for area in next_path]

    insert_group_decision(
        connection,
        case_name=case_name,
        mode=mode,
        frame=frame,
        group_id=str(group_id),
        algorithm=algorithm,
        awareness=awareness,
        current_area=current_area,
        next_path=next_path,
        est_risk_mean=mean(risk_values) if risk_values else 0.0,
        est_risk_max=max(risk_values) if risk_values else 0.0,
        est_risk_min=min(risk_values) if risk_values else 0.0,
        est_risk_var=pvariance(risk_values) if len(risk_values) > 1 else 0.0,
        risk_now=risks.get(current_area, 0.0) if current_area is not None else 0.0,
    )


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
) -> None:
    """
    Compute current nodes, log agent areas, adjust speeds, update paths for each group,
    and record path-choice data.
    """
    risks = get_risk_levels_by_frame(conn, case_name, frame)

    for group_id, group in groups.items():
        try:
            reservation_horizon = _reservation_horizon_for_heuristic(heuristic, horizon_k)

            compute_current_nodes(sim_cfg, group, frame)
            update_group_reserved_edges(
                env_info,
                group,
                frame=frame,
                group_id=group_id,
                horizon_k=reservation_horizon,
            )

            active_ids = {a.id for a in sim_cfg.simulation.agents()}
            group.agents = [aid for aid in group.agents if aid in active_ids]
            group.current_nodes = {
                aid: n for aid, n in group.current_nodes.items() if aid in active_ids
            }

            if not group.agents:
                continue

            agent_areas = {
                agent_id: (current_area, risks.get(current_area, 0.0))
                for agent_id, current_area in group.current_nodes.items()
            }

            insert_agent_areas(
                conn,
                case_name=case_name,
                mode=mode,
                frame=frame,
                agent_areas=agent_areas,
            )

            update_agent_speed_on_stairs(env_info.graph, sim_cfg, group)

            old_path = list(group.path) if group.path else None

            group = update_group_paths(
                sim_cfg,
                risks,
                group,
                env_info,
                threshold,
                frame=frame,
                group_id=group_id,
                heuristic=heuristic,
                beta=beta,
            )

            if group.path != old_path:
                update_group_reserved_edges(
                    env_info,
                    group,
                    frame=frame,
                    group_id=group_id,
                    horizon_k=reservation_horizon,
                )

            record_group_path_data(
                conn,
                case_name=case_name,
                mode=mode,
                frame=frame,
                group_id=str(group_id),
                group=group,
                risks=risks,
            )

            groups[group_id] = group

        except Exception:
            logger.exception(
                "Group processing failed | %s",
                _ctx(
                    frame=frame, group_id=group_id, agents=len(getattr(group, "agents", []) or [])
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
) -> None:
    """
    Advance the simulation and periodically process agent movements and path updates.
    """
    sim = sim_cfg.simulation
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
        )

    last_log_frame = -1
    frame = 0

    while sim.agent_count() > 0:
        sim.iterate()
        iteration = sim.iteration_count()

        if iteration % sim_cfg.every_nth_frame_simulation != 0:
            continue

        frame = iteration // sim_cfg.every_nth_frame_simulation

        if frame % log_every_frames == 0 and frame != last_log_frame:
            last_log_frame = frame
            logger.info("Progress | frame=%d | agents=%d", frame, sim.agent_count())

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
                horizon_k=horizon_k
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
    for pos in positions:
        params = jps.CollisionFreeSpeedModelAgentParameters(
            position=pos,
            journey_id=journey_id,
            stage_id=waypoint_id,
            v0=speed,
        )
        new_agents.append(simulation.add_agent(params))

    return new_agents
