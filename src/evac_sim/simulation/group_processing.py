from __future__ import annotations

from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.agent_area import insert_agent_areas
from evac_sim.simulation.group_path_updates import update_group_paths
from evac_sim.simulation.group_recording import record_group_path_data
from evac_sim.simulation.group_state import (
    reservation_horizon_for_heuristic,
    set_group_speed,
    uses_static_reservations,
    uses_temporal_reservations,
)
from evac_sim.simulation.simulation_logic import (
    clear_group_static_reservation_state,
    release_group_static_reservations,
    restore_group_static_reservations,
    update_agent_speed_on_stairs,
    update_group_static_reservations,
)
from evac_sim.simulation.temporal_capacity import (
    release_temporal_path_reservation,
    reserve_temporal_path,
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

    use_edge_reservations = uses_static_reservations(heuristic)
    use_temporal_reservations = uses_temporal_reservations(heuristic)

    waiting_before_update = getattr(group, "waiting_due_to_congestion", False)

    if use_edge_reservations and not waiting_before_update:
        update_group_static_reservations(
            env_info,
            group,
            frame=frame,
            group_id=group_id,
            horizon_k=reservation_horizon,
        )

    if use_temporal_reservations:
        release_temporal_path_reservation(
            env_info.graph,
            group_id=group_id,
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

    if use_edge_reservations and old_reserved_edges:
        release_group_static_reservations(env_info, group)

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

    if use_edge_reservations:
        if getattr(group, "waiting_due_to_congestion", False):
            clear_group_static_reservation_state(group)

        elif group.path == old_path:
            group.reserved_edges = old_reserved_edges
            group.reserved_group_size = old_reserved_group_size
            restore_group_static_reservations(env_info, group)

        else:
            clear_group_static_reservation_state(group)
            update_group_static_reservations(
                env_info,
                group,
                frame=frame,
                group_id=group_id,
                horizon_k=reservation_horizon,
            )

    elif use_temporal_reservations:
        if getattr(group, "waiting_due_to_congestion", False):
            release_temporal_path_reservation(
                env_info.graph,
                group_id=group_id,
            )
        else:
            reserve_temporal_path(
                env_info.graph,
                group.path,
                group_id=group_id,
                group_size=len(group.agents),
                current_frame=frame,
            )

        clear_group_static_reservation_state(group)

    else:
        clear_group_static_reservation_state(group)

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