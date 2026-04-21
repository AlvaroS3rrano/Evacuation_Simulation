from __future__ import annotations

import logging
from statistics import mean, pvariance

import jupedsim as jps

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.agent_area import insert_agent_areas
from evac_sim.db.repositories.risk import get_risk_levels_by_frame
from evac_sim.db.repositories.group_decisions import insert_group_decision
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.routing.decision_policies import compute_alternative_path, compute_best_available_path
from evac_sim.routing.utils import is_sublist
from evac_sim.routing.heuristics import compute_effective_edge_cost
from evac_sim.simulation.simulation_logic import (
    compute_current_nodes,
    update_agent_speed_on_stairs,
    update_group_reserved_edges,
    release_group_reserved_edges,
    restore_group_reserved_edges,
)

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

def _uses_reservations(heuristic: str) -> bool:
    return heuristic != "none"

def _safe_path_index(path: list | None, node) -> int:
    if not path:
        return -1
    try:
        return path.index(node)
    except ValueError:
        return -1

def _build_subgroup_from_parent(parent: AgentGroup, agent_ids: list[int]) -> AgentGroup:
    return AgentGroup(
        agents=list(agent_ids),
        path=list(parent.path) if parent.path is not None else None,
        current_nodes={
            aid: parent.current_nodes[aid]
            for aid in agent_ids
            if aid in parent.current_nodes
        },
        algorithm=parent.algorithm,
        awareness_level=parent.awareness_level,
        blocked_nodes=list(parent.blocked_nodes),
        wait_until_node=parent.wait_until_node,
        agents_in_stairs=[aid for aid in parent.agents_in_stairs if aid in agent_ids],
        initial_agents_ids=[aid for aid in parent.initial_agents_ids if aid in agent_ids],
        reserved_edges=set(),
        reserved_group_size=0,
    )

def _next_split_group_id(existing_groups: dict, parent_group_id, suffix: str = "lag") -> str:
    base = f"{parent_group_id}__{suffix}"
    candidate = base
    counter = 1

    while candidate in existing_groups:
        counter += 1
        candidate = f"{base}_{counter}"

    return candidate

def split_group_by_progress_threshold(
    group: AgentGroup,
    *,
    threshold: int | None,
) -> tuple[AgentGroup, AgentGroup] | None:
    """
    Split a group in two when lagging or desaligned agents are too far behind
    the most advanced one in the group's current path.

    Agents are moved to a lagging subgroup when:
    - their progress index differs from the maximum by more than `threshold`, or
    - their current node cannot be mapped to the group's current path.
    """
    if threshold is None or threshold < 0:
        return None

    if not group.path or not group.current_nodes or len(group.agents) < 2:
        return None

    indexed_agents: list[tuple[int, int]] = []
    unmapped_ids: list[int] = []

    for aid in group.agents:
        idx = _safe_path_index(group.path, group.current_nodes.get(aid))
        if idx >= 0:
            indexed_agents.append((aid, idx))
        else:
            unmapped_ids.append(aid)

    if not indexed_agents:
        return None

    max_idx = max(idx for _, idx in indexed_agents)

    lagging_ids = [
        aid
        for aid, idx in indexed_agents
        if (max_idx - idx) > threshold
    ]

    lagging_set = set(lagging_ids) | set(unmapped_ids)
    if not lagging_set:
        return None

    leading_ids = [aid for aid in group.agents if aid not in lagging_set]

    if not leading_ids:
        return None

    lead_group = _build_subgroup_from_parent(group, leading_ids)
    lag_group = _build_subgroup_from_parent(group, [aid for aid in group.agents if aid in lagging_set])

    return lead_group, lag_group

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

def _remaining_path_from_node(path: list, current_node):
    try:
        idx = path.index(current_node)
        return path[idx:]
    except ValueError:
        return path


def _path_effective_cost(
    graph,
    path: list,
    *,
    heuristic: str = "none",
    beta: float = 1.0,
    group_size: int = 0,
) -> float:
    if not path or len(path) < 2:
        return float("inf")

    total = 0.0
    for u, v in zip(path, path[1:]):
        total += compute_effective_edge_cost(
            edge_data=graph[u][v],
            heuristic=heuristic,
            beta=beta,
            group_size=group_size,
        )
    return total

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
    congestion_reroute_epsilon: float = 0.10,
) -> AgentGroup:
    """
    Evaluate whether the group should be rerouted.

    Low awareness:
        reroute only when the current policy detects a risk-based trigger.

    High awareness:
        reroute when either:
        1) the current policy detects a risk-based trigger, or
        2) a better alternative route improves the effective cost by at least epsilon.
    """
    agent_ids = group.agents
    if not agent_ids:
        return group

    current_path = group.path
    current_nodes = group.current_nodes
    simulation = sim_cfg.simulation
    waypoints = sim_cfg.waypoints_ids

    to_check = [max(agent_ids, key=lambda aid: current_path.index(current_nodes[aid]))]

    for aid in to_check:
        if not validate_agent(aid, simulation, current_nodes):
            return group

        curr_node = current_nodes[aid]
        idx = try_get_node_index(curr_node, current_path)
        if idx < 0 or idx >= len(current_path) - 1:
            continue

        next_node = current_path[idx + 1]
        group_size = len(group.agents)

        # 1) Risk-triggered alternative
        risk_alt_path = compute_alternative_path(
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

        selected_alt_path = None
        reroute_reason = None

        if risk_alt_path and not is_sublist(risk_alt_path, current_path):
            selected_alt_path = risk_alt_path
            reroute_reason = "risk"

        # 2) Congestion-based proactive reroute for HIGH awareness only
        elif group.awareness_level == 1 and heuristic == "h2":
            best_path = compute_best_available_path(
                exits=sim_cfg.exit_names,
                agent_group=group,
                env_info=env_info,
                current_node=curr_node,
                risk_map=risk_map,
                risk_threshold=threshold,
                gamma=sim_cfg.gamma,
                heuristic=heuristic,
                beta=beta,
            )

            if best_path and not is_sublist(best_path, current_path):
                current_remaining = _remaining_path_from_node(current_path, curr_node)

                current_cost = _path_effective_cost(
                    env_info.graph,
                    current_remaining,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                )

                best_cost = _path_effective_cost(
                    env_info.graph,
                    best_path,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                )

                if best_cost <= (1.0 - congestion_reroute_epsilon) * current_cost:
                    selected_alt_path = best_path
                    reroute_reason = "congestion"

        if selected_alt_path is not None:
            try:
                current_idx = current_path.index(curr_node)
                full_path = current_path[: current_idx + 1] + selected_alt_path[1:]
            except ValueError:
                full_path = selected_alt_path

            journeys = set_journeys(
                simulation,
                curr_node,
                [full_path],
                waypoints,
                sim_cfg.exit_ids,
            )
            new_jid, _ = journeys[curr_node][0]

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
                "Reroute applied | %s | reason=%s | curr=%s next=%s | old_len=%d new_len=%d",
                _ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                reroute_reason,
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

def _process_single_group(
    sim_cfg,
    env_info,
    conn,
    risks: dict,
    groups: dict,
    *,
    case_name: str,
    mode: int,
    frame: int,
    threshold: float,
    heuristic: str,
    beta: float,
    horizon_k: int | None,
    congestion_reroute_epsilon: float,
    group_id,
    group: AgentGroup,
) -> None:
    reservation_horizon = _reservation_horizon_for_heuristic(heuristic, horizon_k)
    use_reservations = _uses_reservations(heuristic)

    if use_reservations:
        update_group_reserved_edges(
            env_info,
            group,
            frame=frame,
            group_id=group_id,
            horizon_k=reservation_horizon,
        )

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
    old_reserved_edges = set(group.reserved_edges)
    old_reserved_group_size = group.reserved_group_size

    if use_reservations:
        release_group_reserved_edges(env_info, group)

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
        congestion_reroute_epsilon=congestion_reroute_epsilon,
    )

    if use_reservations:
        if group.path == old_path:
            group.reserved_edges = old_reserved_edges
            group.reserved_group_size = old_reserved_group_size
            restore_group_reserved_edges(env_info, group)
        else:
            group.reserved_edges = set()
            group.reserved_group_size = 0
            update_group_reserved_edges(
                env_info,
                group,
                frame=frame,
                group_id=group_id,
                horizon_k=reservation_horizon,
            )
    else:
        group.reserved_edges = set()
        group.reserved_group_size = 0

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
) -> None:
    risks = get_risk_levels_by_frame(conn, case_name, frame)

    for original_group_id, original_group in list(groups.items()):
        try:
            group = groups.get(original_group_id)
            if group is None:
                continue

            compute_current_nodes(sim_cfg, group, frame)

            active_ids = {a.id for a in sim_cfg.simulation.agents()}
            group.agents = [aid for aid in group.agents if aid in active_ids]
            group.current_nodes = {
                aid: n for aid, n in group.current_nodes.items() if aid in active_ids
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
                lag_group_id = _next_split_group_id(groups, original_group_id, suffix="lag")

                logger.info(
                    "Group split applied | %s | threshold=%s | lead_agents=%d lag_agents=%d new_group=%s",
                    _ctx(frame=frame, group_id=original_group_id, agents=len(group.agents)),
                    group_split_threshold,
                    len(lead_group.agents),
                    len(lag_group.agents),
                    lag_group_id,
                )

                if _uses_reservations(heuristic):
                    # Remove the previous group edge reservations before dividing the groups
                    release_group_reserved_edges(env_info, group)
                else:
                    group.reserved_edges = set()
                    group.reserved_group_size = 0

                groups[original_group_id] = lead_group
                groups[lag_group_id] = lag_group

                groups_to_process = [
                    (original_group_id, lead_group),
                    (lag_group_id, lag_group),
                ]

            for group_id, aligned_group in groups_to_process:
                if not aligned_group.agents:
                    continue

                _process_single_group(
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
                    group_id=group_id,
                    group=aligned_group,
                )

        except Exception:
            logger.exception(
                "Group processing failed | %s",
                _ctx(
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
            horizon_k=horizon_k,
            congestion_reroute_epsilon=congestion_reroute_epsilon,
            group_split_threshold=group_split_threshold,
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
                horizon_k=horizon_k,
                congestion_reroute_epsilon=congestion_reroute_epsilon,
                group_split_threshold=group_split_threshold,
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
