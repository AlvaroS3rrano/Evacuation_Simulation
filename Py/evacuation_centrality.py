import gurobipy as gp
from gurobipy import GRB
from pathAlgorithms import compute_efficient_paths
import math
import networkx as nx


def evacuationCentralityAlgorithm(G, source, targets, gamma):
    """
    Computes efficient evacuation paths from the source to targets (using the cost tolerance factor gamma)
    and then computes the evacuation centrality (i.e. the maximum number of arc-disjoint paths) via gurobipy.

    Returns a tuple:
       - efficient_paths: list of efficient paths (each path is a list of nodes)
       - evacuation_centrality: optimal integer value of the maximum number of arc-disjoint paths
       - best_paths: subset of efficient_paths selected by the model (those with x[p]=1)
       - agile_scores: a dictionary mapping each efficient path to its agility value (geometric mean of intermediate nodes' centrality)
    """
    # Step 1: Obtain efficient paths (using your compute_efficient_paths function)
    efficient_paths = compute_efficient_paths(G, source, targets, gamma, sort_paths=False)

    if not efficient_paths:
        return [], 0, [], {}

    # Step 2: Build the set of arcs used in the efficient paths and map each path to its arc list.
    path_arcs = []
    arcs_set = set()
    for path in efficient_paths:
        arc_list = []
        for u, v in zip(path, path[1:]):
            arc = (u, v)
            arc_list.append(arc)
            arcs_set.add(arc)
        path_arcs.append(arc_list)

    # Step 3: Define and solve the model in gurobipy.
    model = gp.Model("EvacuationCentrality")
    model.Params.OutputFlag = 0  # Suppress solver output

    # Binary decision variable x[p] for each path p.
    x = model.addVars(range(len(efficient_paths)), vtype=GRB.BINARY, name="x")

    # Constraint: For each arc a in arcs_set, sum of x[p] for paths that use that arc must be <= 1.
    for arc in arcs_set:
        paths_using_arc = [p_idx for p_idx, arcs in enumerate(path_arcs) if arc in arcs]
        if paths_using_arc:
            model.addConstr(gp.quicksum(x[p_idx] for p_idx in paths_using_arc) <= 1, name=f"arc_{arc}")

    # Objective: maximize the sum of x[p] (i.e., maximize the number of arc-disjoint paths).
    model.setObjective(gp.quicksum(x[p_idx] for p_idx in range(len(efficient_paths))), GRB.MAXIMIZE)
    model.optimize()

    if model.status != GRB.OPTIMAL:
        return efficient_paths, 0, [], {}

    evacuation_centrality = int(model.objVal)
    best_paths = [efficient_paths[p_idx] for p_idx in range(len(efficient_paths)) if x[p_idx].X > 0.5]

    # Step 4: Compute a new "agility" score for each efficient path.
    # Instead of using the sum of centrality values, we use the geometric mean of the intermediate nodes' centralities.
    # Here, we use the evacuation betweenness centrality computed as before:
    evacuation_betweenness = {node: 0.0 for node in G.nodes()}
    total_paths = len(efficient_paths)
    if total_paths > 0:
        for path in efficient_paths:
            # Only consider intermediate nodes (exclude first and last)
            for node in path[1:-1]:
                evacuation_betweenness[node] += 1 / total_paths

    agile_scores = {}
    for path in efficient_paths:
        intermediates = path[1:-1]
        if intermediates:
            # Compute product of centrality values for intermediate nodes.
            prod = 1.0
            for node in intermediates:
                prod *= evacuation_betweenness[node]
            # Calculate geometric mean: (product)^(1/number of nodes)
            gm = prod ** (1 / len(intermediates))
        else:
            gm = 0
        agile_scores[tuple(path)] = gm

    scored_paths = [(path, agile_scores[tuple(path)]) for path in efficient_paths]
    scored_paths.sort(key=lambda x: x[1], reverse=True)
    best_agile_paths = [path for path, score in scored_paths]

    return efficient_paths, evacuation_centrality, best_agile_paths, agile_scores


# Example usage:
if __name__ == "__main__":
    # Create a more complex directed graph
    G_complex = nx.DiGraph()

    # Define a set of edges with their costs (e.g., travel times)
    edges = [
        ("A", "B", 2),
        ("A", "C", 4),
        ("B", "D", 1),
        ("B", "E", 5),
        ("C", "D", 1),
        ("C", "F", 3),
        ("D", "E", 2),
        ("D", "G", 3),
        ("E", "G", 2),
        ("E", "H", 4),
        ("F", "H", 2),
        ("G", "I", 3),
        ("H", "I", 3),
        ("F", "I", 4)
    ]

    # Add edges to the graph with the specified cost attribute
    for u, v, cost in edges:
        G_complex.add_edge(u, v, cost=cost)

    # Define the source node and target(s) (exits)
    source = "A"
    targets = ["I"]

    # Set the tolerance factor gamma (e.g., allowing paths with cost up to (1 + gamma) * min_cost)
    gamma = 0.3

    # Call the modified function that calculates evacuation centrality and agility scores
    efficient_paths, evac_centrality, best_paths, agile_scores = evacuationCentralityAlgorithm(
        G_complex, source, targets, gamma
    )

    print("Efficient Paths:")
    for path in efficient_paths:
        print(path)

    print("\nEvacuation Centrality (max number of arc-disjoint paths):", evac_centrality)

    print("\nBest Paths Selected by the ILP model:")
    for path in best_paths:
        print(path)

    print("\nAgility Scores for Each Path (Geometric Mean of Intermediate Nodes' Centralities):")
    for path, score in agile_scores.items():
        print(f"{path}: {score:.4f}")
