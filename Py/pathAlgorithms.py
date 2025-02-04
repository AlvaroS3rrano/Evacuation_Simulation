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
    Computes all efficient paths from a single source to each target node based on a cost tolerance factor.

    Args:
        G (networkx.DiGraph): A directed graph where nodes represent locations and edges have a 'cost' attribute.
        source (node): The source node (starting point for paths).
        targets (list): List of target nodes.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * min_cost (minimum cost among all paths) are considered efficient.

    Returns:
        dict: A dictionary where keys are (source, target) pairs and values are lists of efficient paths (each path is a list of nodes)
              that satisfy the cost tolerance.
    """
    efficient_paths = {}

    # For each target, compute all efficient paths from the source.
    for target in targets:
        # Get all simple paths between source and target.
        all_paths = list(nx.all_simple_paths(G, source=source, target=target))
        if not all_paths:
            continue  # Skip if no path exists.

        # Pre-calculate costs for all paths to avoid recomputation.
        path_costs = [sum(G[u][v]["cost"] for u, v in zip(path, path[1:])) for path in all_paths]
        min_cost = min(path_costs)
        max_allowed_cost = (1 + gamma) * min_cost

        # Filter paths based on the allowed cost tolerance.
        efficient_paths[(source, target)] = [
            path for path, cost in zip(all_paths, path_costs) if cost <= max_allowed_cost
        ]

    return efficient_paths

def centralityMeasuresAlgorithm(G, source, targets, gamma):
    """
    Computes efficient evacuation paths, calculates node centralities (Evacuation Betweenness Centrality),
    and identifies the best paths for the given source based on the centrality scores of the nodes within those paths.

    Args:
        G (networkx.DiGraph): A directed graph where nodes represent locations, and edges have a 'cost' attribute
            representing the travel cost or time between nodes.
        source (node): The source node (starting point of the evacuation paths).
        targets (list): List of target nodes (end points of evacuation paths).
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
            (1 + gamma) * min_cost (minimum cost among all paths) are considered efficient.

    Returns:
        tuple: A tuple containing:
            - efficient_paths (dict): A dictionary with keys as (source, target) pairs and values as lists
              of efficient paths (each path is a list of nodes) that satisfy the cost tolerance.
            - evacuation_betweenness (dict): A dictionary where keys are nodes and values are their
              Evacuation Betweenness Centrality scores, reflecting their importance in efficient paths.
            - best_paths (list): A list of paths (each path is a list of nodes), sorted in descending order
              by the sum of node centrality scores.
    """
    # Step 1: Compute efficient paths for each target from the source.
    efficient_paths = compute_efficient_paths(G, source, targets, gamma)

    # Step 2: Calculate Evacuation Betweenness Centrality for all nodes
    # Only intermediate nodes (excluding the source and target) contribute.
    evacuation_betweenness = {node: 0.0 for node in G.nodes()}

    for paths in efficient_paths.values():
        total_paths = len(paths)
        if total_paths == 0:
            continue  # Skip if there are no efficient paths for this pair.
        for path in paths:
            for node in path[1:-1]:  # Exclude the first and last node (source and target).
                evacuation_betweenness[node] += 1 / total_paths

    # Step 3: Identify the best paths for the given source based on the sum of node centrality scores.
    scored_paths = []
    for (s, _), paths in efficient_paths.items():
        # 's' is always equal to the input source.
        for path in paths:
            # Compute the total centrality score for the entire path.
            total_centrality_score = sum(evacuation_betweenness[node] for node in path)
            scored_paths.append((path, total_centrality_score))

    # Sort the paths in descending order by their centrality scores.
    scored_paths.sort(key=lambda x: x[1], reverse=True)

    # Return only the paths (without the centrality scores), maintaining the order.
    best_paths = [path for path, score in scored_paths]

    return efficient_paths, evacuation_betweenness, best_paths