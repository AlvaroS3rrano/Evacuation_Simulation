import itertools

import math
import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths


def centrality_measures(G, all_paths):
    """
    Compute global betweenness centrality (weighted by 'cost') for every node,
    then score each path by multiplying the centralities of its interior nodes.

    Args:
        G (nx.DiGraph): Directed graph with a 'cost' attribute on each edge.
        all_paths (list of (path, cost)): Tuples where `path` is a list of nodes
                                          and `cost` is the path’s total cost.

    Returns:
        tuple:
            evacuation_betweenness (dict): Mapping node → betweenness value.
            scored_paths (list): Tuples (path, cost, score) where `score` is
                                 the product of interior-node centralities.
    """
    # 1) Compute global betweenness centrality over all node pairs
    node_route_frequency = {node: 0.0 for node in G.nodes()}
    sigma_st = len(all_paths)

    # Calculate betweenness centrality for each node (ignoring source and target nodes)
    if sigma_st > 0:
        for path, _ in all_paths:
            for node in path[1:-1]:  # Exclude source and target nodes
                node_route_frequency[node] += 1 / sigma_st

    # other option could be
    # evacuation_betweenness = nx.betweenness_centrality(G, weight='cost', normalized=True)

    # 2) Score each path by multiplying the centralities of interior nodes
    scored_paths = []
    for path, cost in all_paths:
        interior_nodes = path[1:-1]
        k = len(interior_nodes)

        score = 0.0
        if k > 0:
            log_sum = 0.0
            for node in interior_nodes:
                c = max(node_route_frequency.get(node, 0.0), 1e-12)
                log_sum += math.log(c)

            score = math.exp(log_sum / k)

        scored_paths.append((path, cost, score))

    return node_route_frequency, scored_paths


def collect_k_shortest_paths(G: nx.DiGraph, source, targets, k=50):
    """
    Collects up to k simple paths of minimum cost from the source node to each target node,
    calculates the cost of each path, and applies centrality measures to score them.

    Args:
        G (networkx.DiGraph): Directed graph where edges have a 'cost' attribute.
        source: The source node from which paths start.
        targets (list): A list of target nodes to which paths are calculated.
        k (int): Maximum number of shortest simple paths to collect per target.

    Returns:
        list: A list of (path, cost, centrality_score) tuples for all targets.
    """
    all_paths = []

    for target in targets:
        try:
            # Generator over simple paths sorted by total 'cost'
            paths_gen = shortest_simple_paths(G, source, target, weight="cost")
            # Take only the first k paths
            for path in itertools.islice(paths_gen, k):
                # Compute total cost of this path
                cost = sum(G[u][v]["cost"] for u, v in zip(path, path[1:]))
                all_paths.append((path, cost))
        except nx.NetworkXNoPath:
            # No path exists for this target; skip
            continue

    # Apply your centrality measures function to score and rank
    _, scored_paths = centrality_measures(G, all_paths)
    return scored_paths


def collect_unblocked_paths(paths, blocked_nodes):
    """
    Filters out paths that contain any of the blocked nodes, only if blocked_nodes is not empty.

    Args:
        paths (list): A list of tuples, where each tuple is of the form ([path], cost, centrality_value).
                      'path' is a list of nodes.
        blocked_nodes (list): A list of nodes that are blocked.

    Returns:
        list: A list of paths that do not contain any blocked nodes.
    """
    if blocked_nodes:
        # Filter out paths that contain any blocked nodes
        paths = [
            (path, cost, centrality)
            for (path, cost, centrality) in paths
            if not any(node in blocked_nodes for node in path)
        ]
    return paths


def compute_efficient_paths(paths, gamma):
    """
    Filters paths based on a cost tolerance and computes the efficient paths that satisfy the cost threshold.

    Args:
        paths (list): A list of tuples (path, cost, centrality_value), where each tuple contains:
                      - path (list): The list of nodes in the path.
                      - cost (float): The cost of the path.
                      - centrality_value (float): The centrality value of the path.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * min_cost are considered efficient.

    Returns:
        list: A list of paths that satisfy the cost tolerance, including cost and centrality value.
    """
    # Find the minimum cost from all the paths
    min_cost = min(path[1] for path in paths)
    max_allowed_cost = (1 + gamma) * min_cost

    # Filter paths to include only those that satisfy the cost tolerance
    efficient_paths = [
        (path, cost, centrality) for path, cost, centrality in paths if cost <= max_allowed_cost
    ]

    # Return only the filtered efficient paths
    return efficient_paths
