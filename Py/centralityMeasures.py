import networkx as nx

# Create the directed graph
G = nx.DiGraph()

# Nodes
nodes = [
    "G", "H", "I",
    "D", "E", "F",
    "A", "B", "C",
]
G.add_nodes_from(nodes)

# Edges with travel times (costs)
edges = [
    ("A", "B", {"cost": 3}),
    ("A", "D", {"cost": 3}),
    ("B", "C", {"cost": 3}),
    ("B", "E", {"cost": 3}),
    ("B", "A", {"cost": 3}),
    ("C", "B", {"cost": 3}),
    ("C", "F", {"cost": 3}),
    ("D", "E", {"cost": 3}),
    ("D", "A", {"cost": 3}),
    ("D", "G", {"cost": 3}),
    ("E", "D", {"cost": 3}),
    ("E", "F", {"cost": 3}),
    ("E", "B", {"cost": 3}),
    ("E", "H", {"cost": 3}),
    ("F", "C", {"cost": 3}),
    ("F", "E", {"cost": 3}),
    ("F", "I", {"cost": 3}),
    ("G", "D", {"cost": 3}),
    ("G", "H", {"cost": 3}),
    ("H", "E", {"cost": 3}),
    ("H", "G", {"cost": 3}),
    ("H", "I", {"cost": 3}),
]

G.add_edges_from((u, v, d) for u, v, d in edges)

# Parameters for calculation
sources = ["A"]  # Source nodes
targets = ["I"]  # Target nodes

# Calculate all efficient paths between source-target pairs
gamma = 0.2  # Time tolerance factor


def centralityMeasuresAlgorithm(G, sources, targets, gamma):
    """
    Computes efficient evacuation paths, calculates node centralities (Evacuation Betweenness Centrality),
    and identifies the best path for each source based on the centrality scores of its nodes.

    Args:
        G (networkx.DiGraph): A directed graph where nodes represent locations, and edges have a 'cost' attribute
            representing the travel cost or time between nodes.
        sources (list): List of source nodes (starting points of evacuation paths).
        targets (list): List of target nodes (end points of evacuation paths).
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
            gamma * min_cost are considered efficient.

    Returns:
        tuple: A tuple containing:
            - efficient_paths (dict): A dictionary where keys are (source, target) pairs and values are lists
                of efficient paths that satisfy the cost tolerance.
            - evacuation_betweenness (dict): A dictionary where keys are nodes and values are their
                Evacuation Betweenness Centrality scores, reflecting their importance in efficient paths.
            - best_paths_per_source (dict): A dictionary where keys are source nodes and values are dictionaries
                containing:
                - "best_path" (list): The path with the highest sum of node centralities for that source.
                - "max_centrality_score" (float): The centrality score of the best path.
    """
    # Initialize the dictionary to store efficient paths
    efficient_paths = {}

    # Step 1: Find all efficient paths for each source-target pair
    for source in sources:
        for target in targets:
            # Find all simple paths between source and target
            all_paths = list(nx.all_simple_paths(G, source=source, target=target))

            # Calculate the minimum cost of all paths
            # ["A", "B", "C", "I"] -> zip(path, path[1:]) -> [("A", "B"), ("B", "C"), ("C", "I")]
            min_cost = min(sum(G[u][v]["cost"] for u, v in zip(path, path[1:])) for path in all_paths)

            # Filter paths based on the maximum allowed cost (min_cost * (gamma + 1))
            efficient_paths[(source, target)] = [
                path
                for path in all_paths
                if sum(G[u][v]["cost"] for u, v in zip(path, path[1:])) <= (1 + gamma) * min_cost
            ]

    # Step 2: Calculate Evacuation Betweenness Centrality for all nodes
    evacuation_betweenness = {node: 0 for node in G.nodes}

    for (_, _), paths in efficient_paths.items():
        total_paths = len(paths)
        for path in paths:
            for node in path[1:-1]:  # Only consider intermediate nodes (The source and target are allways in the path)
                evacuation_betweenness[node] += 1 / total_paths

    # Step 3: Identify the path with the highest sum of node centralities
    all_paths_sorted = {}

    for (source, _), paths in efficient_paths.items():
        # Create a list to store paths with their centrality scores
        scored_paths = []

        for path in paths:
            # Calculate the total centrality score for the path
            centrality_score = sum(evacuation_betweenness[node] for node in path)
            scored_paths.append((path, centrality_score))

        # Sort the paths by their centrality scores in descending order
        scored_paths.sort(key=lambda x: x[1], reverse=True)

        # Store the sorted paths and scores for the source
        all_paths_sorted[source] = scored_paths

    return efficient_paths, evacuation_betweenness, all_paths_sorted

efficient_paths, evacuation_betweenness, all_paths_sorted = centralityMeasuresAlgorithm(G, sources, targets, gamma)

# Display results
print("Efficient Paths:")
for (source, target), paths in efficient_paths.items():
    print(f"{source} -> {target}: {paths}")

print("\nEvacuation Betweenness Centrality:")
for node, value in evacuation_betweenness.items():
    print(f"{node}: {value}")

# Display the best path and its score for each source
print("\nPath with the highest Evacuation Betweenness Centrality for each source:")
for source, data in all_paths_sorted.items():
    for path, val in data:
        print(f"Source: {source}")
        print(f"Path: {path}")
        print(f"Centrality Score: {val}\n")
