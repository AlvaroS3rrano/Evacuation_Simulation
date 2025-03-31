import gurobipy as gp
from gurobipy import GRB
from pathAlgorithms import collect_unblocked_paths, compute_efficient_paths
import math
import networkx as nx


def evacuationCentralityAlgorithm(G, source, targets, gamma, lambda_penalty=1.0):
    """
    Computes efficient evacuation paths from the source to targets (using the cost tolerance factor gamma)
    and then computes the evacuation centrality (i.e. the maximum number of arc-disjoint paths) via gurobipy.

    Parameters:
      G: A NetworkX directed graph.
      source: The source node.
      targets: A list of safe target nodes.
      gamma: Tolerance factor (assumed that the collected paths are already efficient).
      lambda_penalty: Penalty parameter for using an arc more than once.

    Returns a tuple:
      - efficient_paths: The list of original efficient paths (each as a list of nodes).
      - evac_centrality: The optimal value of K (penalized evacuation centrality).
      - best_paths: The subset of efficient_paths selected by the model (those with x[p] > 0.5).
      - agile_scores: A dictionary mapping each efficient path to its agility score.
    """
    # Step 1: Collect efficient paths from source to targets.
    # possible_paths = compute_efficient_paths(G, source, targets, gamma, sort_paths=False)
    possible_paths = collect_unblocked_paths(G, source, targets)
    if not possible_paths:
        return [], 0, [], {}

    # Append a dummy node to each path ending at a target.
    # The dummy node is used as a unique sink in the flow conservation constraints.
    dummy = "dummy"
    possible_paths = [path + [dummy] for path in possible_paths if path[-1] in targets]

    # Build list of arcs (tuples) for each path and set of "real" arcs (excluding dummy arcs).
    path_arcs = []
    arcs_set = set()
    for path in possible_paths:
        arc_list = []
        for u, v in zip(path, path[1:]):
            arc = (u, v)
            arc_list.append(arc)
            # Only consider arcs that do not end at the dummy node as real arcs.
            if v != dummy:
                arcs_set.add(arc)
        path_arcs.append(arc_list)

    # Gather all nodes that appear in the paths (including the dummy node).
    nodes_in_paths = set()
    for path in possible_paths:
        for node in path:
            nodes_in_paths.add(node)

    # Create the model.
    model = gp.Model("EvacuationCentralityPenalized")
    model.Params.OutputFlag = 0  # Suppress solver output

    num_paths = len(possible_paths)
    # Continuous decision variables x[p] for each path, relaxed between 0 and 1.
    x = model.addVars(range(num_paths), vtype=GRB.CONTINUOUS, lb=0, ub=1, name="x")

    # Variable K representing the total flow out of the source (i.e. the evacuation centrality).
    K = model.addVar(vtype=GRB.CONTINUOUS, name="K")

    # Penalty variables y for each real arc.
    y = model.addVars(list(arcs_set), vtype=GRB.CONTINUOUS, lb=0, name="y")

    model.update()

    # Flow conservation constraints for each node in the set of nodes in the paths.
    # For each node, compute: (sum of x[p] for paths where the node appears as tail)
    # minus (sum of x[p] for paths where the node appears as head) equals:
    #    K if node == source,
    #   -K if node == dummy,
    #    0 otherwise.
    for node in nodes_in_paths:
        flow_expr = gp.LinExpr()
        for p_idx, path in enumerate(possible_paths):
            for (u, v) in zip(path, path[1:]):
                if u == node:
                    flow_expr.addTerms(1.0, x[p_idx])
                if v == node:
                    flow_expr.addTerms(-1.0, x[p_idx])
        if node == source:
            model.addConstr(flow_expr == K, name=f"flow_{node}")
        elif node == dummy:
            model.addConstr(flow_expr == -K, name=f"flow_{node}")
        else:
            model.addConstr(flow_expr == 0, name=f"flow_{node}")

    # Constraint to penalize multiple use of an arc:
    # For each real arc, the sum of x[p] for the paths using that arc must be <= 1 + y[arc].
    for arc in arcs_set:
        paths_using_arc = [p_idx for p_idx, arcs in enumerate(path_arcs) if arc in arcs]
        if paths_using_arc:
            model.addConstr(gp.quicksum(x[p_idx] for p_idx in paths_using_arc) <= 1 + y[arc],
                            name=f"arc_{arc}")

    # Objective: Maximize K minus the penalty term (lambda_penalty * sum(y)).
    model.setObjective(K - lambda_penalty * gp.quicksum(y[arc] for arc in y.keys()), GRB.MAXIMIZE)

    model.optimize()

    # If the model is not optimal, return default values.
    if model.status != GRB.OPTIMAL:
        return possible_paths, 0, [], {}

    evac_centrality = K.X
    # Retrieve best paths (those with x[p] > 0.5) and remove the dummy node.
    best_paths_full = [possible_paths[p_idx] for p_idx in range(num_paths) if x[p_idx].X > 0.5]
    best_paths = [path[:-1] for path in best_paths_full]  # Remove dummy (last element)

    # Also remove dummy from the complete list of efficient paths.
    efficient_paths = [path[:-1] for path in possible_paths]

    # For this example, agile_scores are not computed and are set to 0.
    agile_scores = {tuple(path): 0 for path in efficient_paths}

    # Helper function to compute the cost of a path (sum of edge costs).
    def compute_path_cost(path, graph):
        total_cost = 0
        for u, v in zip(path, path[1:]):
            total_cost += graph[u][v]['cost']
        return total_cost

    print("Best agile (penalized) paths with their costs:")
    for path in best_paths:
        cost = compute_path_cost(path, G)
        print(f"Path: {path} | Cost: {cost}")
    print("Evacuation centrality (penalized K):", evac_centrality)

    return efficient_paths, evac_centrality, best_paths, agile_scores


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

    print("\nBest Paths Selected by the model:")
    for path in best_paths:
        print(path)

    print("\nAgility Scores for Each Path (Geometric Mean of Intermediate Nodes' Centralities):")
    for path, score in agile_scores.items():
        print(f"{path}: {score:.4f}")
