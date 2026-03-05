# ──────────────────────────────────────────────────────────────────────────────
# Imports from your project (adjust to your final package structure)
# ──────────────────────────────────────────────────────────────────────────────
from .graph_risk import update_all_graph_risks
from .multifloor_paths import getPosiblePaths

# ──────────────────────────────────────────────────────────────────────────────
# Helper functions (local policies)
# ──────────────────────────────────────────────────────────────────────────────


def handle_blocked_node_in_path(best_path, agent_group) -> None:
    """
    Apply a "wait-until-node" policy when the selected path contains blocked nodes.

    If `best_path` includes any node listed in `agent_group.blocked_nodes`, the group is
    instructed to wait until reaching the first blocked node encountered along the path.
    Additionally, the node immediately before that blocked node is added to `blocked_nodes`
    to reduce backtracking behavior.

    Args:
        best_path (list | None): Candidate path as a list of node ids.
        agent_group: Agent group object with:
            - blocked_nodes (list)
            - wait_until_node (node id | None)

    Returns:
        None
    """
    if best_path and any(node in best_path for node in agent_group.blocked_nodes):
        blocked_node = next(node for node in agent_group.blocked_nodes if node in best_path)
        agent_group.wait_until_node = blocked_node

        idx = best_path.index(blocked_node)
        if idx > 0:
            prev_node = best_path[idx - 1]
            if prev_node not in agent_group.blocked_nodes:
                agent_group.blocked_nodes.append(prev_node)


def select_best_alternative_path(
    alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group
):
    """
    Select the best path among candidate alternative paths using neighbor-risk heuristics.

    Strategy:
      1) If multiple neighbors share the minimum risk, prefer a path whose next hop is
         among those minimum-risk neighbors.
      2) Otherwise, iterate neighbors sorted by increasing risk and choose the first path
         whose next hop matches the current neighbor.

    After selection, `handle_blocked_node_in_path` is applied to enforce the wait policy.

    Args:
        alternative_paths (list[list]): Candidate paths.
        neighbors_sorted (list): Neighbors of current node sorted by risk (ascending).
        min_risk_neighbors (list): Neighbors considered best by risk (ties + safe nodes).
        agent_group: Agent group object.

    Returns:
        list | None: Selected path, or None if no suitable path was found.
    """
    best_path = None

    if alternative_paths and neighbors_sorted:
        # Prefer paths that start with one of the minimum-risk neighbors (tie handling)
        if len(min_risk_neighbors) > 1:
            for path in alternative_paths:
                if len(path) > 1 and path[1] in min_risk_neighbors:
                    best_path = path
                    break

            # If no path matched any min-risk neighbor, remove them from consideration
            if best_path is None:
                for cand in min_risk_neighbors:
                    if cand in neighbors_sorted:
                        neighbors_sorted.remove(cand)

        # Otherwise, pick the first path matching the best remaining neighbor order
        if best_path is None:
            for neighbor in neighbors_sorted:
                for path in alternative_paths:
                    if len(path) > 1 and path[1] == neighbor:
                        best_path = path
                        break
                if best_path is not None:
                    break

    handle_blocked_node_in_path(best_path, agent_group)
    return best_path


def _get_possible_paths_with_fallback(EnvInf, current_node, exits, gamma, algo, blocked_nodes):
    """
    Compute paths avoiding blocked nodes first; if no feasible path exists, retry without blocking.

    This implements "soft blocking": blocked nodes are treated as constraints only when feasible.

    Args:
        EnvInf: Environment info.
        current_node: Current node id.
        exits (list): Exit node ids.
        gamma (float): Cost tolerance factor.
        algo (int): Routing objective selector (0 cost-based, 1 betweenness-based).
        blocked_nodes (list): Nodes to exclude if possible.

    Returns:
        list[list]: List of candidate paths (node sequences).
    """
    paths = getPosiblePaths(EnvInf, current_node, exits, gamma, algo, blocked_nodes=blocked_nodes)
    if not paths:
        paths = getPosiblePaths(EnvInf, current_node, exits, gamma, algo, blocked_nodes=[])
    return paths


# ──────────────────────────────────────────────────────────────────────────────
# Replanning policies
# ──────────────────────────────────────────────────────────────────────────────


def compute_low_awareness_alternative_path(
    exits, risk_per_node, next_node, current_node, agent_group, EnvInf, gamma, risk_threshold
):
    """
    Compute an alternative path for low-awareness agents using local (next-hop / neighborhood) risk.

    Policy:
      - If the next planned node is below the risk threshold, no replanning is needed (return None).
      - Otherwise:
          1) Update the graph's node 'risk' attributes.
          2) Mark risky neighbors as blocked (soft constraint).
          3) Compute feasible alternative paths (with fallback if blocking removes all paths).
          4) Select the best path using neighbor-risk heuristics.

    Returns:
        list | None: Selected alternative path, or None if no replanning is needed/possible.
    """
    algo = agent_group.algorithm
    current_path = getattr(agent_group, "path", None)

    # If there is a planned path and the immediate next step is safe, do not replan
    if current_path is not None and risk_per_node.get(next_node, 0.0) < risk_threshold:
        return None

    # Update graph risks so routing decisions reflect current risk estimates
    update_all_graph_risks(EnvInf, risk_per_node)
    G = EnvInf.graph

    # Sort neighbors by risk (lowest first)
    neighbors_sorted = sorted(
        G.neighbors(current_node), key=lambda neighbor: G.nodes[neighbor].get("risk", float("inf"))
    )

    # If the node is isolated, replanning is impossible
    if not neighbors_sorted:
        return None

    # Soft-block neighbors whose risk exceeds the threshold
    for neighbour in neighbors_sorted:
        if (
            risk_per_node.get(neighbour, 0.0) >= risk_threshold
            and neighbour not in agent_group.blocked_nodes
        ):
            agent_group.blocked_nodes.append(neighbour)

    # Identify the "best" neighbors: lowest-risk ones + any neighbor below threshold
    min_risk = G.nodes[neighbors_sorted[0]].get("risk", float("inf"))
    min_risk_neighbors = [
        n
        for n in neighbors_sorted
        if G.nodes[n].get("risk", float("inf")) == min_risk
        or G.nodes[n].get("risk", float("inf")) < risk_threshold
    ]

    # Compute alternative paths (fallback without blocking if needed)
    alternative_paths = _get_possible_paths_with_fallback(
        EnvInf, current_node, exits, gamma, algo, agent_group.blocked_nodes
    )

    return select_best_alternative_path(
        alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group
    )


def compute_high_awareness_alternative_path(
    exits, risk_per_node, current_node, agent_group, EnvInf, gamma, risk_threshold
):
    """
    Compute an alternative path for high-awareness agents by scanning the remaining planned path for risk.

    Policy:
      - Inspect the future nodes of the current planned path.
      - If any future node exceeds `risk_threshold`, trigger replanning and mark those nodes as blocked.
      - Update graph risks and compute alternative feasible paths (soft blocking with fallback).
      - Select the path with minimum cumulative risk along intermediate nodes.

    Returns:
        list | None: Best alternative path found, or None if no replanning is needed/possible.
    """
    algo = agent_group.algorithm
    current_path = agent_group.path

    dangerous_path = False

    if current_path is not None:
        try:
            index = current_path.index(current_node)
            for node in current_path[index + 1 :]:
                if risk_per_node.get(node, 0.0) >= risk_threshold:
                    if node not in agent_group.blocked_nodes:
                        agent_group.blocked_nodes.append(node)
                    dangerous_path = True
        except ValueError:
            dangerous_path = True
    else:
        dangerous_path = True

    if not dangerous_path:
        return None

    # Update graph risks so routing reflects latest estimates
    update_all_graph_risks(EnvInf, risk_per_node)
    G = EnvInf.graph

    # Compute alternative paths (fallback without blocking if needed)
    alternative_paths = _get_possible_paths_with_fallback(
        EnvInf, current_node, exits, gamma, algo, agent_group.blocked_nodes
    )

    if not alternative_paths:
        return None

    best_path = None
    best_risk = float("inf")

    for path in alternative_paths:
        if not path or len(path) < 2:
            continue

        # Cumulative risk over intermediate nodes (excluding current node and exit)
        path_risk = sum(G.nodes[node].get("risk", 0.0) for node in path[1:-1])
        if path_risk < best_risk:
            best_risk = path_risk
            best_path = path

    return best_path


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────


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
    Dispatch alternative-path computation based on the group's awareness level and wait policy.

    If a wait condition is active (`agent_group.wait_until_node`), replanning is skipped until
    at least one agent reaches that node. Once waiting is cleared, the function dispatches
    to the corresponding replanning policy (low/high awareness).

    Returns:
        list | None: Alternative path if computed, otherwise None.
    """
    wait_node = agent_group.wait_until_node

    # Clear wait condition if it is inactive or satisfied by any agent in the group
    if wait_node is None or (
        agent_group.current_nodes and wait_node in agent_group.current_nodes.values()
    ):
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
