from __future__ import annotations

from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.agent_area import insert_agent_areas
from evac_sim.simulation.group_path_updates import update_group_paths
from evac_sim.simulation.group_recording import record_group_path_data
from evac_sim.simulation.group_state import (
    reservation_horizon_for_heuristic,
    set_group_speed,
    uses_reservations,
)
from evac_sim.simulation.simulation_logic import (
    release_group_reserved_edges,
    restore_group_reserved_edges,
    update_agent_speed_on_stairs,
    update_group_reserved_edges,
)


def process_single_group(
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
    no_path_policy: str,
    group_id: Any,
    group: AgentGroup,
) -> None:
    reservation_horizon = reservation_horizon_for_heuristic(
        heuristic,
        horizon_k,
    )
    use_reservations = uses_reservations(heuristic)

    waiting_before_update = getattr(group, "waiting_due_to_congestion", False)

    if use_reservations and not waiting_before_update:
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

    old_path = list(group.path) if group.path else None
    old_reserved_edges = set(group.reserved_edges)
    old_reserved_group_size = group.reserved_group_size

    if use_reservations and old_reserved_edges:
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
        horizon_k=horizon_k,
        no_path_policy=no_path_policy,
    )

    if use_reservations:
        if getattr(group, "waiting_due_to_congestion", False):
            group.reserved_edges = set()
            group.reserved_group_size = 0

        elif group.path == old_path:
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

    if getattr(group, "waiting_due_to_congestion", False):
        set_group_speed(sim_cfg.simulation, group, 0.0)
    else:
        update_agent_speed_on_stairs(env_info.graph, sim_cfg, group)

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