import networkx as nx

def get_sortest_path(G, source, targets):
    """
    Finds and returns the target node with the shortest weighted path from the given source node.

    This function uses Dijkstra's algorithm to compute the shortest paths and their corresponding
    distances from the 'source' node to all other nodes in the graph 'G'. It then iterates over the
    provided list of 'targets' to determine which target is reachable with the minimum total weight.
    If none of the target nodes are reachable from the source, the function returns None.

    Parameters:
        G (networkx.Graph): The graph on which to compute the shortest paths.
        source (node): The starting node from which paths are computed.
        targets (list): A list of target nodes for which the shortest path is to be determined.

    Returns:
        min_target (node or None): The target node with the shortest weighted path from the source,
                                   or None if no target is reachable.
    """
    # Compute the shortest paths and distances using Dijkstra's algorithm
    distances, paths = nx.single_source_dijkstra(G, source=source, weight='cost')

    # Initialize variables to store the target with the minimum distance
    min_distance = float('inf')
    min_target = None

    # Loop through the list of targets and find the one with the shortest weighted distance
    for target in targets:
        if target in distances and distances[target] < min_distance:
            min_distance = distances[target]
            min_target = target

    if min_target is not None:
        return paths[min_target]
    else:
        return None


def compute_efficient_paths(G, source, targets, gamma):
    """
    Computes all efficient paths from a single source to a set of target nodes based on a cost tolerance factor.

    This function collects all simple paths from the source to any of the target nodes, computes the cost
    for each path, and then filters the paths to include only those with a cost less than or equal to
    (1 + gamma) * global_min_cost (where global_min_cost is the smallest cost among all paths).

    Args:
        G (networkx.DiGraph): A directed graph where nodes represent locations and edges have a 'cost' attribute.
        source (node): The source node (starting point for paths).
        targets (list): List of target nodes.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * global_min_cost are considered efficient.

    Returns:
        list: A list of efficient paths (each path is a list of nodes) that satisfy the cost tolerance across all targets.
    """
    # Gather all simple paths from source to each target in one list.
    all_paths = []
    for target in targets:
        for path in nx.all_simple_paths(G, source=source, target=target):
            all_paths.append(path)

    if not all_paths:
        return []  # No paths found

    # Compute the cost for each path.
    path_costs = [
        sum(G[u][v]["cost"] for u, v in zip(path, path[1:]))
        for path in all_paths
    ]

    # Determine the global minimum cost among all paths.
    min_cost = min(path_costs)
    max_allowed_cost = (1 + gamma) * min_cost

    # Filter and return only those paths that satisfy the cost tolerance.
    efficient_paths = [
        path for path, cost in zip(all_paths, path_costs)
        if cost <= max_allowed_cost
    ]

    return efficient_paths

def centralityMeasuresAlgorithm(G, source, targets, gamma):
    """
    Computes efficient evacuation paths, calculates node centralities (Evacuation Betweenness Centrality),
    and identifies the best paths for the given source based on the centrality scores of the nodes within those paths.

    This version assumes that compute_efficient_paths returns a single list of efficient paths (each being a list of nodes)
    from the source to any of the target nodes.

    Args:
        G (networkx.DiGraph): A directed graph where nodes represent locations and edges have a 'cost' attribute.
        source (node): The source node (starting point of the evacuation paths).
        targets (list): List of target nodes (end points of evacuation paths).
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
            (1 + gamma) * min_cost (minimum cost among all paths) are considered efficient.

    Returns:
        tuple: A tuple containing:
            - efficient_paths (list): A list of efficient paths (each path is a list of nodes) that satisfy the cost tolerance.
            - evacuation_betweenness (dict): A dictionary where keys are nodes and values are their
              Evacuation Betweenness Centrality scores, reflecting their importance in efficient paths.
            - best_paths (list): A list of paths (each path is a list of nodes), sorted in descending order
              by the sum of node centrality scores.
    """
    # Step 1: Compute efficient paths from the source to all targets.
    # The updated compute_efficient_paths returns a single list of paths.
    efficient_paths = compute_efficient_paths(G, source, targets, gamma)

    # Step 2: Calculate Evacuation Betweenness Centrality for all nodes.
    # Only intermediate nodes (excluding the source and target nodes in each path) contribute.
    evacuation_betweenness = {node: 0.0 for node in G.nodes()}
    total_paths = len(efficient_paths)

    if total_paths > 0:
        for path in efficient_paths:
            # Contribute only from intermediate nodes (skip first and last node)
            for node in path[1:-1]:
                evacuation_betweenness[node] += 1 / total_paths

    # Step 3: Identify the best paths based on the sum of node centrality scores along each path.
    scored_paths = []
    for path in efficient_paths:
        total_centrality_score = sum(evacuation_betweenness[node] for node in path)
        scored_paths.append((path, total_centrality_score))

    # Sort the paths in descending order by their centrality scores.
    scored_paths.sort(key=lambda x: x[1], reverse=True)

    # Return only the paths (without the centrality scores), maintaining the order.
    best_paths = [path for path, score in scored_paths]

    return efficient_paths, evacuation_betweenness, best_paths