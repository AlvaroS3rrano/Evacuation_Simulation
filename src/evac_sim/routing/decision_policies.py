from plotly.graph_objs.indicator.gauge import threshold

from .graph_risk import update_all_graph_risks
from .multifloor_paths import get_posible_paths

def _get_group_size(agent_group) -> int:
    return len(agent_group.agents)

def handle_blocked_node_in_path(best_path, agent_group) -> None:
    """
    Update the wait target when the selected path contains blocked nodes.
    """
    blocked_nodes = agent_group.blocked_nodes

    if best_path and any(node in best_path for node in blocked_nodes):
        blocked_node = next(node for node in blocked_nodes if node in best_path)
        agent_group.wait_until_node = blocked_node

        idx = best_path.index(blocked_node)
        if idx > 0:
            prev_node = best_path[idx - 1]
            if prev_node not in blocked_nodes:
                blocked_nodes.append(prev_node)

        agent_group.blocked_nodes = blocked_nodes


def _get_possible_paths_with_fallback(
    env_info,
    current_node,
    exits,
    gamma,
    algo,
    blocked_nodes,
    heuristic="none",
    beta=1.0,
    group_size=0,
):
    """
    Get feasible paths, retrying without blocked nodes if needed.
    """
    paths = get_posible_paths(
        env_info,
        current_node,
        exits,
        gamma,
        algo,
        blocked_nodes=blocked_nodes,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
    )

    if not paths:
        paths = get_posible_paths(
            env_info,
            current_node,
            exits,
            gamma,
            algo,
            blocked_nodes=[],
            heuristic=heuristic,
            beta=beta,
            group_size=group_size,
        )

    return paths


def _select_path_by_active_strategy(alternative_paths, agent_group):
    """
    Select the first path from an already sorted candidate list.
    """
    if not alternative_paths:
        return None

    best_path = alternative_paths[0]
    handle_blocked_node_in_path(best_path, agent_group)
    return best_path

def compute_initial_path(
    exits,
    agent_group,
    env_info,
    source_node,
    risk_per_node=None,
    gamma=0.4,
    heuristic="none",
    beta=1.0,
    group_size=None,
):
    """
    Compute the initial evacuation path for a group before the simulation starts.

    Unlike compute_alternative_path(), this function does not depend on an
    already existing path or on next_node, because it is used during group
    initialization.
    """
    blocked_nodes = agent_group.blocked_nodes

    if risk_per_node is not None:
        update_all_graph_risks(env_info, risk_per_node)

    if group_size is None:
        group_size = _get_group_size(agent_group)

    alternative_paths = _get_possible_paths_with_fallback(
        env_info=env_info,
        current_node=source_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
    )

    return _select_path_by_active_strategy(alternative_paths, agent_group)

def compute_low_awareness_alternative_path(
    exits,
    risk_per_node,
    next_node,
    current_node,
    agent_group,
    env_info,
    gamma,
    risk_threshold,
    heuristic="none",
    beta=1.0,
):
    """
    Recompute the path if the next node is unsafe.
    """
    current_path = getattr(agent_group, "path", None)
    blocked_nodes = agent_group.blocked_nodes

    if current_path is None or next_node is None:
        return None

    if risk_per_node is None:
        return None

    if risk_per_node.get(next_node, 0.0) < risk_threshold:
        return None

    if next_node not in blocked_nodes:
        blocked_nodes.append(next_node)
        agent_group.blocked_nodes = blocked_nodes

    update_all_graph_risks(env_info, risk_per_node)

    group_size = _get_group_size(agent_group)

    alternative_paths = _get_possible_paths_with_fallback(
        env_info=env_info,
        current_node=current_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
    )

    return _select_path_by_active_strategy(alternative_paths, agent_group)

def compute_high_awareness_alternative_path(
    exits,
    risk_per_node,
    current_node,
    agent_group,
    env_info,
    gamma,
    risk_threshold,
    heuristic="none",
    beta=1.0,
):
    """
    Recompute the path if any remaining node is unsafe.
    """
    current_path = agent_group.path
    blocked_nodes = agent_group.blocked_nodes
    dangerous_path = False

    if risk_per_node is None:
        return None

    if current_path is not None:
        try:
            index = current_path.index(current_node)

            for node in current_path[index + 1:]:
                if risk_per_node.get(node, 0.0) >= risk_threshold:
                    if node not in blocked_nodes:
                        blocked_nodes.append(node)
                    dangerous_path = True
        except ValueError:
            dangerous_path = True
    else:
        dangerous_path = True

    if not dangerous_path:
        return None

    agent_group.blocked_nodes = blocked_nodes
    update_all_graph_risks(env_info, risk_per_node)

    group_size = _get_group_size(agent_group)

    alternative_paths = _get_possible_paths_with_fallback(
        env_info=env_info,
        current_node=current_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
    )

    return _select_path_by_active_strategy(alternative_paths, agent_group)


def compute_alternative_path(
    exits,
    agent_group,
    env_info,
    current_node=None,
    next_node=None,
    risk_map=None,
    risk_threshold=0.5,
    gamma=0.4,
    heuristic="none",
    beta=1.0,
):
    """
    Dispatch rerouting based on the group's awareness level.
    """
    wait_node = getattr(agent_group, "wait_until_node", None)
    current_nodes = getattr(agent_group, "current_nodes", None)

    if wait_node is None or (current_nodes and wait_node in current_nodes.values()):
        agent_group.wait_until_node = None

    if agent_group.awareness_level == 0:
        return compute_low_awareness_alternative_path(
            exits=exits,
            risk_per_node=risk_map,
            next_node=next_node,
            current_node=current_node,
            agent_group=agent_group,
            env_info=env_info,
            gamma=gamma,
            risk_threshold=risk_threshold,
            heuristic=heuristic,
            beta=beta,
        )

    if agent_group.awareness_level == 1:
        return compute_high_awareness_alternative_path(
            exits=exits,
            risk_per_node=risk_map,
            current_node=current_node,
            agent_group=agent_group,
            env_info=env_info,
            gamma=gamma,
            risk_threshold=risk_threshold,
            heuristic=heuristic,
            beta=beta,
        )

    return None

def compute_best_available_path(
    exits,
    agent_group,
    env_info,
    current_node,
    risk_map=None,
    risk_threshold=0.5,
    gamma=0.4,
    heuristic="none",
    beta=1.0,
):
    blocked_nodes = agent_group.blocked_nodes
    group_size = _get_group_size(agent_group)

    alternative_paths = _get_possible_paths_with_fallback(
        env_info=env_info,
        current_node=current_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
    )

    safe_paths = [
        p for p in alternative_paths
        if all(risk_map.get(node, 0.0) <= risk_threshold for node in p)
    ]

    if safe_paths:
        return safe_paths[0]
    else:
        return None