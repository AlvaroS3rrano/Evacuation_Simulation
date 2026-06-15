from __future__ import annotations

from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.agent_area import insert_agent_areas
from evac_sim.simulation.capacity_reservations import (
    PathSchedule,
    get_capacity_reservation_manager,
)
from evac_sim.simulation.group_path_updates import update_group_paths
from evac_sim.simulation.group_recording import record_group_path_data
from evac_sim.simulation.group_state import (
    clear_group_waiting_due_to_congestion,
    mark_group_waiting_due_to_congestion,
    representative_current_node,
    reservation_horizon_for_heuristic,
    set_group_speed,
)
from evac_sim.simulation.simulation_logic import (
    clear_group_static_reservation_state,
    update_agent_speed_on_stairs,
)


def _get_existing_next_edge_schedule(
    *,
    manager,
    group_id: Any,
    group: AgentGroup,
    current_node: Any,
    frame: int,
) -> PathSchedule | None:
    """
    Return the current reservation schedule if it already contains a reservation
    for the next edge of the group's current path.

    This is important when a group has a future reservation. In that case, the
    group must wait, but the reservation should not be released and recreated on
    every frame.
    """
    schedule = manager.group_reservations.get(group_id)

    if schedule is None:
        return None

    if not group.path or current_node not in group.path:
        return None

    current_index = group.path.index(current_node)

    if current_index >= len(group.path) - 1:
        return schedule

    next_edge = ("edge", group.path[current_index], group.path[current_index + 1])

    for interval in schedule.intervals:
        if interval.resource != next_edge:
            continue

        if frame <= interval.end_frame:
            return schedule

    return None


def ensure_group_has_capacity_to_move(
    *,
    env_info,
    group: AgentGroup,
    group_id: Any,
    heuristic: str,
    horizon_k: int | None,
    frame: int,
) -> bool:
    """
    Ensure that a group is allowed to move according to the capacity reservation
    model.

    For heuristic='none', movement is always allowed because this is the baseline.

    For h1/h2/h3:
      - the group may move only if the next edge is currently reserved;
      - if the reservation exists but starts in the future, the group waits;
      - if there is no reservation, the manager tries to reserve the remaining path;
      - if no feasible reservation exists, the group waits.
    """
    if heuristic == "none":
        return True

    manager = get_capacity_reservation_manager(env_info.graph)
    current_node = representative_current_node(group)

    if current_node is None or not group.path:
        return False

    manager.release_passed_resources(
        group_id,
        current_node,
        frame,
    )

    if manager.has_valid_next_reservation(
        group_id,
        group.path,
        current_node,
        frame,
    ):
        group.reserved_schedule = manager.group_reservations.get(group_id)
        return True

    existing_schedule = _get_existing_next_edge_schedule(
        manager=manager,
        group_id=group_id,
        group=group,
        current_node=current_node,
        frame=frame,
    )

    if existing_schedule is not None:
        group.reserved_schedule = existing_schedule
        return False

    horizon_edges = reservation_horizon_for_heuristic(
        heuristic,
        horizon_k,
    )

    if current_node in group.path:
        current_index = group.path.index(current_node)
        remaining_path = list(group.path[current_index:])
    else:
        remaining_path = list(group.path)

    if len(remaining_path) < 2:
        return True

    schedule = manager.find_earliest_feasible_schedule(
        remaining_path,
        group_size=len(group.agents),
        start_frame=frame,
        horizon_edges=horizon_edges,
        ignore_group_id=group_id,
    )

    if schedule is None:
        group.reserved_schedule = None
        return False

    reserved = manager.reserve_path(
        group_id,
        remaining_path,
        len(group.agents),
        schedule,
    )

    if not reserved:
        group.reserved_schedule = None
        return False

    group.reserved_schedule = schedule

    if schedule.first_departure_frame > frame:
        return False

    return True


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
    """
    Process a single group during one simulation frame.

    Capacity-aware heuristics h1/h2/h3 are controlled exclusively through
    CapacityReservationManager. The old temporal_capacity.py reservation system
    must not be used here.
    """
    env_info.graph.graph["current_frame"] = frame

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

    has_capacity = ensure_group_has_capacity_to_move(
        env_info=env_info,
        group=group,
        group_id=group_id,
        heuristic=heuristic,
        horizon_k=horizon_k,
        frame=frame,
    )

    if not has_capacity:
        mark_group_waiting_due_to_congestion(
            group,
            frame=frame,
        )
        set_group_speed(
            sim_cfg.simulation,
            group,
            0.0,
        )
    else:
        clear_group_waiting_due_to_congestion(group)
        update_agent_speed_on_stairs(
            env_info.graph,
            sim_cfg,
            group,
        )

    clear_group_static_reservation_state(group)

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