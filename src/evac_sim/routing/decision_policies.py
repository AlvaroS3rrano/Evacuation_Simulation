from .graph_risk import update_all_graph_risks
from .multifloor_paths import getPosiblePaths


def handle_blocked_node_in_path(best_path, agent_group) -> None:
    """
    Update the wait target when the selected path contains blocked nodes.
    """
    blocked_nodes = getattr(agent_group, "blocked_nodes", [])

    if best_path and any(node in best_path for node in blocked_nodes):
        blocked_node = next(node for node in blocked_nodes if node in best_path)
        agent_group.wait_until_node = blocked_node

        idx = best_path.index(blocked_node)
        if idx > 0:
            prev_node = best_path[idx - 1]
            if prev_node not in blocked_nodes:
                blocked_nodes.append(prev_node)

        agent_group.blocked_nodes = blocked_nodes


def _get_possible_paths_with_fallback(EnvInf, current_node, exits, gamma, algo, blocked_nodes):
    """
    Get feasible paths, retrying without blocked nodes if needed.
    """
    paths = getPosiblePaths(
        EnvInf,
        current_node,
        exits,
        gamma,
        algo,
        blocked_nodes=blocked_nodes,
    )

    if not paths:
        paths = getPosiblePaths(
            EnvInf,
            current_node,
            exits,
            gamma,
            algo,
            blocked_nodes=[],
        )

    return paths


def _select_path_by_active_strategy(alternative_paths, agent_group):
    """
    Return the first path from the ordered candidate list.
    """
    if not alternative_paths:
        return None

    best_path = alternative_paths[0]
    handle_blocked_node_in_path(best_path, agent_group)
    return best_path


def compute_low_awareness_alternative_path(
    exits,
    risk_per_node,
    next_node,
    current_node,
    agent_group,
    EnvInf,
    gamma,
    risk_threshold,
):
    """
    Recompute the path if the next node is unsafe.
    """
    current_path = getattr(agent_group, "path", None)
    blocked_nodes = getattr(agent_group, "blocked_nodes", [])

    if current_path is None or next_node is None:
        return None

    if risk_per_node is None:
        return None

    if risk_per_node.get(next_node, 0.0) < risk_threshold:
        return None

    if next_node not in blocked_nodes:
        blocked_nodes.append(next_node)
        agent_group.blocked_nodes = blocked_nodes

    update_all_graph_risks(EnvInf, risk_per_node)

    alternative_paths = _get_possible_paths_with_fallback(
        EnvInf=EnvInf,
        current_node=current_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
    )

    return _select_path_by_active_strategy(alternative_paths, agent_group)


def compute_high_awareness_alternative_path(
    exits,
    risk_per_node,
    current_node,
    agent_group,
    EnvInf,
    gamma,
    risk_threshold,
):
    """
    Recompute the path if any remaining node is unsafe.
    """
    current_path = getattr(agent_group, "path", None)
    blocked_nodes = getattr(agent_group, "blocked_nodes", [])
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
    update_all_graph_risks(EnvInf, risk_per_node)

    alternative_paths = _get_possible_paths_with_fallback(
        EnvInf=EnvInf,
        current_node=current_node,
        exits=exits,
        gamma=gamma,
        algo=agent_group.algorithm,
        blocked_nodes=blocked_nodes,
    )

    return _select_path_by_active_strategy(alternative_paths, agent_group)


def compute_alternative_path(
    exits,
    agent_group,
    EnvInf,
    current_node=None,
    next_node=None,
    risk_per_node=None,
    risk_threshold=0.5,
    gamma=0.4,
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
            risk_per_node=risk_per_node,
            next_node=next_node,
            current_node=current_node,
            agent_group=agent_group,
            EnvInf=EnvInf,
            gamma=gamma,
            risk_threshold=risk_threshold,
        )

    if agent_group.awareness_level == 1:
        return compute_high_awareness_alternative_path(
            exits=exits,
            risk_per_node=risk_per_node,
            current_node=current_node,
            agent_group=agent_group,
            EnvInf=EnvInf,
            gamma=gamma,
            risk_threshold=risk_threshold,
        )

    return None