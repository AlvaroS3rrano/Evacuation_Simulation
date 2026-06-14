from __future__ import annotations

import logging
import math
from typing import Any

from evac_sim.core.agent_group import AgentGroup
from evac_sim.routing.decision_policies import (
    compute_alternative_path,
    compute_best_available_path,
)
from evac_sim.routing.path_algorithms import compute_path_effective_cost
from evac_sim.routing.utils import is_sublist
from evac_sim.simulation.group_state import (
    apply_group_path,
    clear_group_waiting_due_to_congestion,
    ctx,
    mark_group_waiting_due_to_congestion,
    remaining_path_from_node,
    representative_current_node,
    safe_path_index,
    validate_agent,
)

logger = logging.getLogger(__name__)

H2_REROUTE_COOLDOWN_FRAMES = 120
H2_MAX_DETOUR_FACTOR = 1.35
H2_BACKTRACK_REQUIRED_COST_FACTOR = 0.60


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
        return candidate_cost <= H2_BACKTRACK_REQUIRED_COST_FACTOR * current_cost

    return True

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
        mark_group_waiting_due_to_congestion(group, frame=frame)
        return group

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
    )

    if best_path is None:
        mark_group_waiting_due_to_congestion(group, frame=frame)

        logger.debug(
            "Group keeps waiting due to congestion | %s | current_node=%s no_path_count=%d",
            ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
            curr_node,
            group.no_path_count,
        )

        return group

    apply_group_path(
        sim_cfg=sim_cfg,
        group=group,
        current_node=curr_node,
        full_path=best_path,
    )

    clear_group_waiting_due_to_congestion(group)

    logger.debug(
        "Waiting group resumed | %s | current_node=%s path=%s",
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
            mark_group_waiting_due_to_congestion(group, frame=frame)

        return group

    valid_agent_ids = [
        aid
        for aid in agent_ids
        if aid in current_nodes and safe_path_index(current_path, current_nodes[aid]) >= 0
    ]

    if not valid_agent_ids:
        if no_path_policy == "wait":
            mark_group_waiting_due_to_congestion(group, frame=frame)

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
        )

        selected_alt_path = None
        reroute_reason = None

        if risk_alt_path and not is_sublist(risk_alt_path, current_path):
            selected_alt_path = risk_alt_path
            reroute_reason = "risk"

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
                )

                best_cost = compute_path_effective_cost(
                    env_info.graph,
                    best_path,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                    horizon_k=horizon_k,
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

            apply_group_path(
                sim_cfg=sim_cfg,
                group=group,
                current_node=curr_node,
                full_path=full_path,
            )

            if reroute_reason == "congestion" and len(selected_alt_path) >= 2:
                group.last_congestion_reroute_frame = frame
                group.last_congestion_reroute_edge = (
                    curr_node,
                    selected_alt_path[1],
                )

            clear_group_waiting_due_to_congestion(group)

            logger.debug(
                "Reroute applied | %s | reason=%s | curr=%s next=%s | old_len=%d new_len=%d",
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
            and heuristic in {"h2", "h3"}
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
            )

            if best_path is None:
                mark_group_waiting_due_to_congestion(group, frame=frame)

                logger.debug(
                    "Group waits due to no congestion-feasible path | %s | current_node=%s",
                    ctx(frame=frame, group_id=group_id, agents=len(agent_ids)),
                    curr_node,
                )

    return group