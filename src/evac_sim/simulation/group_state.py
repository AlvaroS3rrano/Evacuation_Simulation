from __future__ import annotations

from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.envs.journey_configuration import set_journeys


def ctx(
    *,
    frame: int | None = None,
    group_id: Any | None = None,
    agents: int | None = None,
) -> str:
    parts: list[str] = []

    if frame is not None:
        parts.append(f"frame={frame}")

    if group_id is not None:
        parts.append(f"group={group_id}")

    if agents is not None:
        parts.append(f"agents={agents}")

    return " | ".join(parts)


def reservation_horizon_for_heuristic(
    heuristic: str,
    horizon_k: int | None,
) -> int | None:
    if heuristic == "h1":
        return None

    if heuristic == "h2":
        return horizon_k if horizon_k is not None else 3

    return None


def uses_reservations(heuristic: str) -> bool:
    return heuristic != "none"


def safe_path_index(path: list | None, node: Any) -> int:
    if not path:
        return -1

    try:
        return path.index(node)
    except ValueError:
        return -1


def remaining_path_from_node(path: list | None, current_node: Any) -> list:
    if not path or current_node is None:
        return []

    try:
        idx = path.index(current_node)
        return path[idx:]
    except ValueError:
        return list(path)


def validate_agent(
    agent_id: int,
    *,
    active_ids: set[int],
    current_nodes: dict,
) -> bool:
    return agent_id in active_ids and agent_id in current_nodes


def set_group_speed(simulation, group: AgentGroup, speed: float) -> None:
    active_ids = {agent.id for agent in simulation.agents()}

    for agent_id in group.agents:
        if agent_id not in active_ids:
            continue

        simulation.agent(agent_id).model.v0 = speed


def mark_group_waiting_due_to_congestion(
    group: AgentGroup,
    *,
    frame: int,
) -> None:
    group.waiting_due_to_congestion = True

    if group.waiting_since_frame is None:
        group.waiting_since_frame = frame

    group.no_path_count += 1


def clear_group_waiting_due_to_congestion(group: AgentGroup) -> None:
    group.waiting_due_to_congestion = False
    group.waiting_since_frame = None


def representative_current_node(group: AgentGroup) -> Any | None:
    if not group.agents or not group.current_nodes:
        return None

    if not group.path:
        return group.current_nodes.get(group.agents[0])

    best_agent_id = None
    best_index = -1

    for agent_id in group.agents:
        current_node = group.current_nodes.get(agent_id)

        if current_node is None:
            continue

        idx = safe_path_index(group.path, current_node)

        if idx > best_index:
            best_index = idx
            best_agent_id = agent_id

    if best_agent_id is None:
        return group.current_nodes.get(group.agents[0])

    return group.current_nodes.get(best_agent_id)


def apply_group_path(
    *,
    sim_cfg,
    group: AgentGroup,
    current_node: Any,
    full_path: list,
) -> None:
    simulation = sim_cfg.simulation

    journeys = set_journeys(
        simulation,
        current_node,
        [full_path],
        sim_cfg.waypoints_ids,
        sim_cfg.exit_ids,
    )

    if current_node not in journeys or not journeys[current_node]:
        raise ValueError(
            f"Could not create journey for current_node={current_node}, path={full_path}"
        )

    new_jid, _ = journeys[current_node][0]

    for agent_id in group.agents:
        node = group.current_nodes.get(agent_id)

        try:
            node_idx = full_path.index(node)
            next_stage_node = full_path[min(node_idx + 1, len(full_path) - 1)]
        except ValueError:
            next_stage_node = full_path[1] if len(full_path) > 1 else full_path[0]

        stage_id = sim_cfg.waypoints_ids.get(
            next_stage_node,
            sim_cfg.exit_ids.get(next_stage_node),
        )

        if stage_id is None:
            raise KeyError(
                f"No stage found for next_stage_node={next_stage_node}"
            )

        simulation.switch_agent_journey(agent_id, new_jid, stage_id)

    group.path = full_path