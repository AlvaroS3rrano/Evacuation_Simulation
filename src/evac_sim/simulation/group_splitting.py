from __future__ import annotations

from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation.group_state import safe_path_index


def build_subgroup_from_parent(
    parent: AgentGroup,
    agent_ids: list[int],
) -> AgentGroup:
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
        agents_in_stairs=[
            aid for aid in parent.agents_in_stairs if aid in agent_ids
        ],
        initial_agents_ids=[
            aid for aid in parent.initial_agents_ids if aid in agent_ids
        ],
        reserved_edges=set(),
        reserved_group_size=0,
        waiting_due_to_congestion=parent.waiting_due_to_congestion,
        waiting_since_frame=parent.waiting_since_frame,
        no_path_count=parent.no_path_count,
    )


def next_split_group_id(
    existing_groups: dict,
    parent_group_id: Any,
    suffix: str = "lag",
) -> str:
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
    if threshold is None or threshold < 0:
        return None

    if group.waiting_due_to_congestion:
        return None

    if not group.path or not group.current_nodes or len(group.agents) < 2:
        return None

    indexed_agents: list[tuple[int, int]] = []
    unmapped_ids: list[int] = []

    for aid in group.agents:
        idx = safe_path_index(group.path, group.current_nodes.get(aid))

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

    lead_group = build_subgroup_from_parent(group, leading_ids)
    lag_group = build_subgroup_from_parent(
        group,
        [aid for aid in group.agents if aid in lagging_set],
    )

    return lead_group, lag_group