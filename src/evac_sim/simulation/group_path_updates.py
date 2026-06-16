from __future__ import annotations

import logging
import math
from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.routing.decision_policies import (
    compute_alternative_path,
    compute_best_available_path,
)
from evac_sim.routing.multifloor_paths import get_possible_paths
from evac_sim.routing.path_algorithms import compute_path_effective_cost
from evac_sim.routing.utils import is_sublist
from evac_sim.simulation.capacity_reservations import get_capacity_reservation_manager
from evac_sim.simulation.group_state import (
    apply_group_path,
    clear_group_waiting_due_to_congestion,
    ctx,
    mark_group_waiting_due_to_congestion,
    remaining_path_from_node,
    representative_current_node,
    reservation_horizon_for_heuristic,
    safe_path_index,
    validate_agent,
)

logger = logging.getLogger(__name__)

H2_REROUTE_COOLDOWN_FRAMES = 120
H2_MAX_DETOUR_FACTOR = 1.35
H2_BACKTRACK_REQUIRED_COST_FACTOR = 0.60

H3_REROUTE_COOLDOWN_FRAMES = 90
H3_MAX_CANDIDATE_PATHS = 25
H3_MAX_WAIT_FRAMES = 300
H3_MAX_ARRIVAL_DELAY_FRAMES = 600
H3_MAX_DETOUR_FACTOR = 1.50
H3_MIN_ARRIVAL_IMPROVEMENT_FRAMES = 75


def _path_base_cost(G, path: list | None) -> float:
    if not path or len(path) < 2:
        return float("inf")

    try:
        return compute_path_effective_cost(
            G,
            path,
            heuristic="none",
        )
    except (KeyError, TypeError):
        return float("inf")


def _is_immediate_backtrack(
    *,
    current_path: list,
    curr_node: Any,
    candidate_path: list,
) -> bool:
    if not candidate_path or len(candidate_path) < 2:
        return False

    current_idx = safe_path_index(
        current_path,
        curr_node,
    )

    if current_idx <= 0:
        return False

    previous_node = current_path[current_idx - 1]

    return candidate_path[1] == previous_node


def _undoes_last_h2_reroute(
    *,
    group: AgentGroup,
    curr_node: Any,
    candidate_path: list,
) -> bool:
    if not candidate_path or len(candidate_path) < 2:
        return False

    last_edge = getattr(
        group,
        "last_congestion_reroute_edge",
        None,
    )

    if last_edge is None:
        return False

    candidate_edge = (
        curr_node,
        candidate_path[1],
    )

    return candidate_edge == (
        last_edge[1],
        last_edge[0],
    )


def _is_h2_reroute_on_cooldown(
    *,
    group: AgentGroup,
    frame: int,
) -> bool:
    last_frame = getattr(
        group,
        "last_congestion_reroute_frame",
        None,
    )

    if last_frame is None:
        return False

    return frame - last_frame < H2_REROUTE_COOLDOWN_FRAMES


def _should_accept_h2_congestion_reroute(
    *,
    G,
    group: AgentGroup,
    current_path: list,
    current_remaining: list,
    candidate_path: list,
    curr_node: Any,
    frame: int,
    current_cost: float,
    candidate_cost: float,
) -> bool:
    """
    Keep h2 local, but prevent unstable reroutes.

    h2 should avoid immediate congestion, but it should not:
      - reroute every few frames,
      - go straight back to the previous node,
      - undo the previous reroute,
      - take a very long detour just because the local horizon is cheaper.
    """
    if not candidate_path or len(candidate_path) < 2:
        return False

    if candidate_path[0] != curr_node:
        return False

    if _is_h2_reroute_on_cooldown(
        group=group,
        frame=frame,
    ):
        return False

    current_base_cost = _path_base_cost(
        G,
        current_remaining,
    )

    candidate_base_cost = _path_base_cost(
        G,
        candidate_path,
    )

    if (
        math.isfinite(current_base_cost)
        and math.isfinite(candidate_base_cost)
        and candidate_base_cost > H2_MAX_DETOUR_FACTOR * current_base_cost
    ):
        return False

    is_backtrack = _is_immediate_backtrack(
        current_path=current_path,
        curr_node=curr_node,
        candidate_path=candidate_path,
    )

    undoes_last_reroute = _undoes_last_h2_reroute(
        group=group,
        curr_node=curr_node,
        candidate_path=candidate_path,
    )

    if is_backtrack or undoes_last_reroute:
        return False

    return True

def _h3_reroute_state(env_info) -> dict:
    return env_info.graph.graph.setdefault(
        "h3_temporal_reroute_state",
        {},
    )


def _is_h3_reroute_on_cooldown(
    *,
    env_info,
    group_id: Any,
    frame: int,
) -> bool:
    state = _h3_reroute_state(env_info).get(
        group_id,
        {},
    )

    last_frame = state.get("last_frame")

    if last_frame is None:
        return False

    return frame - int(last_frame) < H3_REROUTE_COOLDOWN_FRAMES


def _mark_h3_temporal_reroute(
    *,
    env_info,
    group_id: Any,
    frame: int,
    edge: tuple[Any, Any] | None,
) -> None:
    _h3_reroute_state(env_info)[group_id] = {
        "last_frame": frame,
        "last_edge": edge,
    }


def _h3_attempt_arrival_frame(attempt) -> float:
    if attempt.schedule is None:
        return float("inf")

    return float(attempt.schedule.arrival_frame)


def _select_h3_temporal_capacity_path(
    *,
    sim_cfg,
    env_info,
    group: AgentGroup,
    group_id: Any,
    current_node: Any,
    current_path: list | None,
    risk_map: dict,
    threshold: float,
    frame: int,
    beta: float,
    require_improvement: bool,
) -> list | None:
    """
    Select the best h3 path by real temporal feasibility.

    h3 differs from h1/h2 because it evaluates multiple candidate routes and
    chooses the one with the earliest feasible arrival frame according to the
    current CapacityReservationManager state.

    This function only scores candidate paths. It does not reserve them.
    The reservation is still performed later by _apply_path_with_capacity_check().
    """
    if current_node is None:
        return None

    manager = get_capacity_reservation_manager(env_info.graph)

    manager.release_passed_resources(
        group_id,
        current_node,
        frame,
    )

    current_remaining = None

    if current_path:
        current_remaining = remaining_path_from_node(
            current_path,
            current_node,
        )

    candidate_paths = get_possible_paths(
        env_info,
        current_node,
        sim_cfg.exit_names,
        sim_cfg.gamma,
        group.algorithm,
        blocked_nodes=group.blocked_nodes,
        heuristic="h3",
        beta=beta,
        group_size=len(group.agents),
        group_id=group_id,
        horizon_k=None,
    )

    candidates: list[list] = []

    if current_remaining and len(current_remaining) >= 2:
        candidates.append(current_remaining)

    for path in candidate_paths:
        if not path or len(path) < 2:
            continue

        if path[0] != current_node:
            continue

        if any(risk_map.get(node, 0.0) > threshold for node in path):
            continue

        if tuple(path) not in {tuple(candidate) for candidate in candidates}:
            candidates.append(path)

    if not candidates:
        logger.info(
            "H3 no feasible candidate | %s | current_node=%s current_path_head=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            current_remaining[:8] if current_remaining else None,
        )
        return None

    candidates = sorted(
        candidates,
        key=lambda path: (
            _path_base_cost(env_info.graph, path),
            len(path),
            tuple(path),
        ),
    )[:H3_MAX_CANDIDATE_PATHS]

    current_base_cost = float("inf")

    if current_remaining and len(current_remaining) >= 2:
        current_base_cost = _path_base_cost(
            env_info.graph,
            current_remaining,
        )

    scored_candidates = []

    for path in candidates:
        if (
                current_path
                and require_improvement
                and _is_immediate_backtrack(
            current_path=current_path,
            curr_node=current_node,
            candidate_path=path,
        )
        ):
            continue

        attempt = manager.attempt_earliest_feasible_schedule(
            path,
            group_size=len(group.agents),
            start_frame=frame,
            horizon_edges=None,
            ignore_group_id=group_id,
        )

        if attempt.schedule is None:
            continue

        arrival_frame = float(attempt.schedule.arrival_frame)
        wait_frames = float(attempt.schedule.wait_frames)
        base_cost = _path_base_cost(
            env_info.graph,
            path,
        )

        if arrival_frame - frame > H3_MAX_ARRIVAL_DELAY_FRAMES:
            continue

        if wait_frames > H3_MAX_WAIT_FRAMES:
            continue

        if (
                math.isfinite(current_base_cost)
                and current_base_cost > 0
                and base_cost > current_base_cost * H3_MAX_DETOUR_FACTOR
        ):
            continue

        scored_candidates.append(
            (
                arrival_frame,
                wait_frames,
                base_cost,
                path,
                attempt.schedule,
            )
        )

    if not scored_candidates:
        logger.info(
            "H3 no temporally feasible candidate | %s | current_node=%s "
            "candidates=%s current_path_head=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            len(candidates),
            current_remaining[:8] if current_remaining else None,
        )
        return None

    scored_candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            tuple(item[3]),
        )
    )

    best_arrival, best_wait, best_base_cost, best_path, best_schedule = scored_candidates[0]

    current_arrival = float("inf")

    if current_remaining and len(current_remaining) >= 2:
        current_attempt = manager.attempt_earliest_feasible_schedule(
            current_remaining,
            group_size=len(group.agents),
            start_frame=frame,
            horizon_edges=None,
            ignore_group_id=group_id,
        )
        current_arrival = _h3_attempt_arrival_frame(current_attempt)

    logger.info(
        "H3 candidates evaluated | %s | current_node=%s candidates=%s "
        "feasible=%s current_arrival=%s best_arrival=%s best_wait=%s "
        "best_path_head=%s",
        ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
        current_node,
        len(candidates),
        len(scored_candidates),
        current_arrival if math.isfinite(current_arrival) else None,
        best_arrival,
        best_wait,
        best_path[:8],
    )

    if not require_improvement:
        return best_path

    if current_remaining and tuple(best_path) == tuple(current_remaining):
        logger.debug(
            "H3 route unchanged | %s | current_node=%s arrival=%s path_head=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            best_arrival,
            best_path[:8],
        )
        return None

    if _is_h3_reroute_on_cooldown(
            env_info=env_info,
            group_id=group_id,
            frame=frame,
    ) and math.isfinite(current_arrival):
        logger.debug(
            "H3 route unchanged on cooldown | %s | current_node=%s "
            "current_arrival=%s best_arrival=%s path_head=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            current_arrival,
            best_arrival,
            best_path[:8],
        )
        return None

    improvement_frames = current_arrival - best_arrival

    if math.isfinite(current_arrival) and improvement_frames < H3_MIN_ARRIVAL_IMPROVEMENT_FRAMES:
        logger.debug(
            "H3 route unchanged due to small improvement | %s | current_node=%s "
            "improvement=%s current_arrival=%s best_arrival=%s path_head=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            improvement_frames,
            current_arrival,
            best_arrival,
            best_path[:8],
        )
        return None

    logger.info(
        "H3 route selected | %s | current_node=%s improvement=%s "
        "current_arrival=%s selected_arrival=%s selected_wait=%s "
        "selected_path_head=%s",
        ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
        current_node,
        improvement_frames if math.isfinite(current_arrival) else None,
        current_arrival if math.isfinite(current_arrival) else None,
        best_arrival,
        best_wait,
        best_path[:8],
    )

    return best_path

def _existing_capacity_schedule_status(
    *,
    env_info,
    group: AgentGroup,
    group_id: Any,
    current_node: Any,
    frame: int,
) -> str:
    manager = get_capacity_reservation_manager(env_info.graph)

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
        return "ready"

    schedule = manager.group_reservations.get(group_id)

    if schedule is None:
        group.reserved_schedule = None
        return "none"

    if not group.path or current_node not in group.path:
        group.reserved_schedule = None
        return "none"

    current_index = group.path.index(current_node)

    if current_index >= len(group.path) - 1:
        group.reserved_schedule = schedule
        return "ready"

    next_edge = ("edge", group.path[current_index], group.path[current_index + 1])
    current_bucket = manager.bucket_for_frame(frame)

    for interval in schedule.intervals:
        if interval.resource != next_edge:
            continue

        if interval.start_bucket <= current_bucket <= interval.end_bucket:
            group.reserved_schedule = schedule
            return "ready"

        if current_bucket < interval.start_bucket:
            group.reserved_schedule = schedule
            return "pending"

    group.reserved_schedule = None
    return "none"


def _reserve_capacity_for_path(
    *,
    env_info,
    group: AgentGroup,
    group_id: Any,
    current_node: Any,
    full_path: list,
    heuristic: str,
    horizon_k: int | None,
    frame: int,
) -> tuple[bool, bool]:
    """
    Reserve capacity for the path before it is applied.

    Returns:
      - reserved: whether a reservation was created or not needed.
      - can_depart_now: whether the first reserved edge can be used now.
    """
    if heuristic == "none":
        return True, True

    reservation_path = remaining_path_from_node(
        full_path,
        current_node,
    )

    if not reservation_path or len(reservation_path) < 2:
        return True, True

    manager = get_capacity_reservation_manager(env_info.graph)

    movement_path = reservation_path[:2]

    attempt = manager.attempt_earliest_feasible_schedule(
        movement_path,
        group_size=len(group.agents),
        start_frame=frame,
        horizon_edges=1,
        ignore_group_id=group_id,
    )

    if attempt.schedule is None:
        group.reserved_schedule = None
        group.waiting_resource = attempt.blocked_resource

        usage = None

        if attempt.blocked_resource is not None and frame % 250 == 0:
            usage = manager.debug_resource_usage(
                attempt.blocked_resource,
                frame,
            )

        logger.info(
            "Path capacity blocked | %s | current_node=%s blocked_resource=%s "
            "retry_frame=%s reason=%s path=%s usage=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            attempt.blocked_resource,
            attempt.earliest_retry_frame,
            attempt.reason,
            movement_path,
            usage,
        )

        return False, False

    reserved = manager.reserve_path(
        group_id,
        movement_path,
        len(group.agents),
        attempt.schedule,
    )

    if not reserved:
        group.reserved_schedule = None
        group.waiting_resource = attempt.blocked_resource

        logger.warning(
            "Path capacity reservation race/failure | %s | current_node=%s "
            "blocked_resource=%s path=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            attempt.blocked_resource,
            movement_path,
        )

        return False, False

    group.reserved_schedule = attempt.schedule
    group.waiting_resource = attempt.blocked_resource

    if attempt.schedule.first_departure_frame > frame:
        logger.info(
            "Capacity pending | %s | current_node=%s blocked_resource=%s "
            "wait_frames=%s path=%s",
            ctx(frame=frame, group_id=group_id, agents=len(group.agents)),
            current_node,
            attempt.blocked_resource,
            attempt.schedule.first_departure_frame - frame,
            movement_path,
        )

        return True, False

    manager.remove_group_from_waiting_queues(group_id)
    group.waiting_resource = None

    return True, True


def _apply_path_with_capacity_check(
    *,
    sim_cfg,
    env_info,
    group: AgentGroup,
    group_id: Any,
    current_node: Any,
    full_path: list,
    heuristic: str,
    horizon_k: int | None,
    frame: int,
) -> bool:
    """
    Apply a new group path after checking local movement capacity.

    Longer temporal reservations may be used for scoring and route selection,
    but physical movement should only be blocked by the next immediate edge/node.
    This prevents full-route schedules from producing stop-and-go movement.
    """
    reserved, can_depart_now = _reserve_capacity_for_path(
        env_info=env_info,
        group=group,
        group_id=group_id,
        current_node=current_node,
        full_path=full_path,
        heuristic=heuristic,
        horizon_k=horizon_k,
        frame=frame,
    )

    if not reserved:
        mark_group_waiting_due_to_congestion(
            group,
            frame=frame,
            resource=getattr(group, "waiting_resource", None),
        )
        return False

    apply_group_path(
        sim_cfg=sim_cfg,
        group=group,
        current_node=current_node,
        full_path=full_path,
    )

    if can_depart_now:
        clear_group_waiting_due_to_congestion(group)
        return True

    mark_group_waiting_due_to_congestion(
        group,
        frame=frame,
        resource=getattr(group, "waiting_resource", None),
    )
    return False


def _try_resume_waiting_group(
    *,
    sim_cfg,
    risk_map: dict,
    group: AgentGroup,
    env_info,
    threshold: float,
    frame: int,
    group_id: Any,
    heuristic: str,
    beta: float,
    horizon_k: int | None,
) -> AgentGroup:
    agent_ids = group.agents
    curr_node = representative_current_node(group)

    if curr_node is None:
        mark_group_waiting_due_to_congestion(
            group,
            frame=frame,
            resource=getattr(group, "waiting_resource", None),
        )
        return group

    if heuristic != "none":
        schedule_status = _existing_capacity_schedule_status(
            env_info=env_info,
            group=group,
            group_id=group_id,
            current_node=curr_node,
            frame=frame,
        )

        if schedule_status == "ready":
            clear_group_waiting_due_to_congestion(group)
            return group

        if schedule_status == "pending":
            return group

    if heuristic == "h3" and group.awareness_level == 1:
        best_path = _select_h3_temporal_capacity_path(
            sim_cfg=sim_cfg,
            env_info=env_info,
            group=group,
            group_id=group_id,
            current_node=curr_node,
            current_path=group.path,
            risk_map=risk_map,
            threshold=threshold,
            frame=frame,
            beta=beta,
            require_improvement=False,
        )
    else:
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
            horizon_k=horizon_k,
            group_id=group_id,
        )

    if best_path is None:
        mark_group_waiting_due_to_congestion(
            group,
            frame=frame,
            resource=getattr(group, "waiting_resource", None),
        )

        logger.debug(
            "Group keeps waiting due to congestion | %s | current_node=%s no_path_count=%d",
            ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
            curr_node,
            group.no_path_count,
        )

        return group

    can_depart_now = _apply_path_with_capacity_check(
        sim_cfg=sim_cfg,
        env_info=env_info,
        group=group,
        group_id=group_id,
        current_node=curr_node,
        full_path=best_path,
        heuristic=heuristic,
        horizon_k=horizon_k,
        frame=frame,
    )

    if can_depart_now:
        logger.debug(
            "Waiting group resumed | %s | current_node=%s path=%s",
            ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
            curr_node,
            best_path,
        )
    else:
        logger.debug(
            "Waiting group reserved future path or keeps waiting | %s | current_node=%s path=%s",
            ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
            curr_node,
            best_path,
        )

    return group


def update_group_paths(
    sim_cfg,
    risk_map: dict,
    group: AgentGroup,
    env_info,
    threshold: float = 0.5,
    *,
    frame: int,
    group_id: Any,
    heuristic: str = "none",
    beta: float = 1.0,
    congestion_reroute_epsilon: float = 0.10,
    horizon_k: int | None = None,
    no_path_policy: str = "raise",
) -> AgentGroup:
    env_info.graph.graph["current_frame"] = frame

    agent_ids = group.agents

    if not agent_ids:
        return group

    if getattr(group, "waiting_due_to_congestion", False):
        return _try_resume_waiting_group(
            sim_cfg=sim_cfg,
            risk_map=risk_map,
            group=group,
            env_info=env_info,
            threshold=threshold,
            frame=frame,
            group_id=group_id,
            heuristic=heuristic,
            beta=beta,
            horizon_k=horizon_k,
        )

    current_path = group.path
    current_nodes = group.current_nodes
    simulation = sim_cfg.simulation

    if not current_path:
        if no_path_policy == "wait":
            mark_group_waiting_due_to_congestion(
                group,
                frame=frame,
                resource=getattr(group, "waiting_resource", None),
            )

        return group

    valid_agent_ids = [
        aid
        for aid in agent_ids
        if aid in current_nodes
        and safe_path_index(current_path, current_nodes[aid]) >= 0
    ]

    if not valid_agent_ids:
        if no_path_policy == "wait":
            mark_group_waiting_due_to_congestion(
                group,
                frame=frame,
                resource=getattr(group, "waiting_resource", None),
            )

        return group

    active_ids = {agent.id for agent in simulation.agents()}

    to_check = [
        max(
            valid_agent_ids,
            key=lambda aid: current_path.index(current_nodes[aid]),
        )
    ]

    for aid in to_check:
        if not validate_agent(
            aid,
            active_ids=active_ids,
            current_nodes=current_nodes,
        ):
            return group

        curr_node = current_nodes[aid]
        idx = safe_path_index(current_path, curr_node)

        if idx < 0 or idx >= len(current_path) - 1:
            continue

        next_node = current_path[idx + 1]
        group_size = len(group.agents)

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
            horizon_k=horizon_k,
            group_id=group_id,
        )

        selected_alt_path = None
        reroute_reason = None

        if risk_alt_path and not is_sublist(risk_alt_path, current_path):
            selected_alt_path = risk_alt_path
            reroute_reason = "risk"

        elif group.awareness_level == 1 and heuristic == "h3":
            best_path = _select_h3_temporal_capacity_path(
                sim_cfg=sim_cfg,
                env_info=env_info,
                group=group,
                group_id=group_id,
                current_node=curr_node,
                current_path=current_path,
                risk_map=risk_map,
                threshold=threshold,
                frame=frame,
                beta=beta,
                require_improvement=True,
            )

            if best_path and not is_sublist(best_path, current_path):
                selected_alt_path = best_path
                reroute_reason = "h3_temporal"

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
                horizon_k=horizon_k,
                group_id=group_id,
            )

            if best_path and not is_sublist(best_path, current_path):
                current_remaining = remaining_path_from_node(
                    current_path,
                    curr_node,
                )

                current_cost = compute_path_effective_cost(
                    env_info.graph,
                    current_remaining,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                    horizon_k=horizon_k,
                    group_id=group_id,
                )

                best_cost = compute_path_effective_cost(
                    env_info.graph,
                    best_path,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                    horizon_k=horizon_k,
                    group_id=group_id,
                )

                if (
                    best_cost <= (1.0 - congestion_reroute_epsilon) * current_cost
                    and _should_accept_h2_congestion_reroute(
                        G=env_info.graph,
                        group=group,
                        current_path=current_path,
                        current_remaining=current_remaining,
                        candidate_path=best_path,
                        curr_node=curr_node,
                        frame=frame,
                        current_cost=current_cost,
                        candidate_cost=best_cost,
                    )
                ):
                    selected_alt_path = best_path
                    reroute_reason = "congestion"

        if selected_alt_path is not None:
            try:
                current_idx = current_path.index(curr_node)
                full_path = current_path[: current_idx + 1] + selected_alt_path[1:]
            except ValueError:
                full_path = selected_alt_path

            if _is_immediate_backtrack(
                    current_path=current_path,
                    curr_node=curr_node,
                    candidate_path=selected_alt_path,
            ):
                logger.warning(
                    "Reroute backtrack detected | %s | reason=%s curr=%s "
                    "old_next=%s new_next=%s old_path=%s selected_alt=%s",
                    ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                    reroute_reason,
                    curr_node,
                    next_node,
                    selected_alt_path[1] if len(selected_alt_path) > 1 else None,
                    current_path[:10],
                    selected_alt_path[:10],
                )

            can_depart_now = _apply_path_with_capacity_check(
                sim_cfg=sim_cfg,
                env_info=env_info,
                group=group,
                group_id=group_id,
                current_node=curr_node,
                full_path=full_path,
                heuristic=heuristic,
                horizon_k=horizon_k,
                frame=frame,
            )

            if (
                    can_depart_now
                    and reroute_reason == "congestion"
                    and len(selected_alt_path) >= 2
            ):
                group.last_congestion_reroute_frame = frame
                group.last_congestion_reroute_edge = (
                    curr_node,
                    selected_alt_path[1],
                )

            if (
                    can_depart_now
                    and reroute_reason == "h3_temporal"
                    and len(selected_alt_path) >= 2
            ):
                _mark_h3_temporal_reroute(
                    env_info=env_info,
                    group_id=group_id,
                    frame=frame,
                    edge=(
                        curr_node,
                        selected_alt_path[1],
                    ),
                )

            logger.debug(
                "Reroute %s | %s | reason=%s | curr=%s next=%s | old_len=%d new_len=%d",
                "applied" if can_depart_now else "reserved_or_waiting",
                ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                reroute_reason,
                curr_node,
                next_node,
                len(current_path),
                len(full_path),
            )

            return group

    if (
            no_path_policy == "wait"
            and heuristic in {"h1", "h2", "h3"}
            and group.awareness_level == 1
    ):
        curr_node = representative_current_node(group)

        if curr_node is not None:
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
                horizon_k=horizon_k,
                group_id=group_id,
            )

            if best_path is None:
                mark_group_waiting_due_to_congestion(
                    group,
                    frame=frame,
                    resource=getattr(group, "waiting_resource", None),
                )

                logger.debug(
                    "Group waits due to no congestion-feasible path | %s | current_node=%s",
                    ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                    curr_node,
                )

    return group