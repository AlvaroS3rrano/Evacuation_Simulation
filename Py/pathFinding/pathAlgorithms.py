import networkx as nx

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
    evacuation_betweenness = nx.betweenness_centrality(
        G,
        weight="cost",
        normalized=True
    )

    # 2) Score each path by multiplying the centralities of interior nodes
    scored_paths = []
    for path, cost in all_paths:
        score = 1.0
        # skip the first and last node (source and target)
        for node in path[1:-1]:
            score *= evacuation_betweenness.get(node, 0.0)
        scored_paths.append((path, cost, score))

    return evacuation_betweenness, scored_paths

def collect_all_paths(G: nx.DiGraph, source, targets):
    """
    Collects all simple paths from the source node to the target nodes, calculates the cost of each path,
    and applies centrality measures to score them.

    Args:
        G (networkx.DiGraph): The directed graph where nodes represent locations and edges have a 'cost' attribute.
        source (node): The source node from which paths start.
        targets (list): A list of target nodes to which paths are calculated.

    Returns:
        list: A list of paths with their associated costs and centrality scores.
    """
    paths = []
    # Collect all simple paths from source to each target node
    for target in targets:
        for path in nx.all_simple_paths(G, source=source, target=target):
            # Calculate the cost of each path
            path_cost = sum(G[u][v]["cost"] for u, v in zip(path, path[1:]))
            paths.append((path, path_cost))

    # Calculate centrality measures and score the paths
    _, paths = centrality_measures(G, paths)
    return paths

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
            (path, cost, centrality) for (path, cost, centrality) in paths
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
        (path, cost, centrality) for path, cost, centrality in paths
        if cost <= max_allowed_cost
    ]

    # Return only the filtered efficient paths
    return efficient_paths
