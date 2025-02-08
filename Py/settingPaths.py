
from Py.pathAlgorithms import *
def update_graph_risks(G, risk_per_node):
    """
    Updates the risk values for each node in the graph based on the provided risk mapping.

    Args:
        G (networkx.Graph): The graph whose nodes will have their risk attributes updated.
        risk_per_node (dict): A dictionary mapping node identifiers to their corresponding risk values.
    """
    # Iterate over each node and its associated risk value in the risk_per_node dictionary.
    for node, risk in risk_per_node.items():
        # Check if the node exists in the graph to avoid updating non-existent nodes.
        if G.has_node(node):
            # Update the 'risk' attribute of the node in the graph.
            G.nodes[node]['risk'] = risk


def select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors):
    """
    Selects the best alternative path based on the provided alternative paths and neighbor lists.

    If both 'alternative_paths' and 'neighbors_sorted' are not empty, the function performs the following:

    1. If there are multiple candidate neighbors (i.e., len(min_risk_neighbors) > 1), it iterates through
       'alternative_paths' to find the first path whose second node is among the candidate neighbors.
       - Once a matching path is found, it is stored as 'best_path' and the iteration stops.
       - After that, all candidate neighbors in 'min_risk_neighbors' are removed from 'neighbors_sorted'
         to prevent reconsideration.

    2. If no best path has been selected in the previous step, the function then iterates through the
       remaining 'neighbors_sorted'. For each neighbor, it checks all 'alternative_paths' for a path where the
       second node exactly matches the current neighbor. If such a path is found, it is selected as 'best_path'
       and the loops exit.

    Parameters:
        alternative_paths (list): A list of alternative paths (each path is a list of nodes).
        neighbors_sorted (list): A list of neighbors sorted by risk.
        min_risk_neighbors (list): A list of candidate neighbors that have the minimum risk.

    Returns:
        list or None: The selected best alternative path if found, or None if no valid path is found.
    """
    best_path = None
    if alternative_paths and neighbors_sorted:
        # If there are multiple candidate neighbors, try to select the first valid path from alternative_paths.
        if len(min_risk_neighbors) > 1:
            for path in alternative_paths:
                if len(path) > 1 and path[1] in min_risk_neighbors:
                    best_path = path
                    break
            # Remove candidate neighbors from neighbors_sorted to avoid reconsidering them.
            for candidate in min_risk_neighbors:
                if candidate in neighbors_sorted:
                    neighbors_sorted.remove(candidate)

        # If no best_path has been found yet, iterate through the sorted neighbors.
        if best_path is None:
            for neighbor in neighbors_sorted:
                for path in alternative_paths:
                    if len(path) > 1 and path[1] == neighbor:
                        best_path = path
                        break  # Found a valid alternative path.
                if best_path:
                    break  # Exit once a valid path is found.
    return best_path
def compute_low_Knowledge_alternative_path(exits, risk_per_node, next_node, current_node, agent_group, G, gamma, risk_threshold):
    """
    Computes an alternative path based on node risk values and the selected algorithm.
    If the risk of the next node is below the threshold, no update is needed and None is returned.

    Args:
        exits (list): List of exits.
        risk_per_node (dict): Mapping of each node to its risk value.
        next_node: The node following the current node in the current path.
        current_node: The current node in the path.
        agent_group (AgentGroup): An AgentGroup instance containing:
            - agents (list): List of agent IDs.
            - path (list): List representing the group's current path.
            - algorithm (int): Identifier for the algorithm used.
            - knowledge_level (int): The knowledge level of the agents.
        G: The graph representing the environment.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * global_min_cost are considered efficient.
        risk_threshold (float): Threshold above which a node is considered unsafe.
    Returns:
        list or None: The best alternative path if one is found, or None if no update is needed or found.
    """

    algo = agent_group.algorithm
    current_path = getattr(agent_group, 'path', None)

    if current_path is not None:
        # If the risk of the next node is below the threshold, no update is needed.
        if risk_per_node[next_node] < risk_threshold:
            return None

        # Update the graph with the risk values for each node.
        update_graph_risks(G, risk_per_node)

    # Sort the neighbors of the current_node by their risk (lowest risk first).
    neighbors_sorted = sorted(
        G.neighbors(current_node),
        key=lambda neighbor: G.nodes[neighbor].get('risk', float('inf'))
    )

    # If a current path is provided, remove its starting node from the neighbors (if applicable).
    # to prevent going backwards
    if current_path is not None and len(current_path) > 0:
        previous_node = current_path[0]
        if current_node != previous_node and previous_node in neighbors_sorted:
            neighbors_sorted.remove(previous_node)

    # Determine the minimum risk among the neighbors.
    min_risk = G.nodes[neighbors_sorted[0]].get('risk', float('inf'))
    # Filter neighbors that have the same (lowest) risk or have a safe risk value.
    min_risk_neighbors = [n for n in neighbors_sorted if G.nodes[n].get('risk', float('inf')) == min_risk or G.nodes[n].get('risk', float('inf')) < risk_threshold]

    best_path = None

    if algo == 1:

        # Get alternative paths using the centralityMeasuresAlgorithm.
        _, _, alternative_paths = centralityMeasuresAlgorithm(
            G, current_node, exits, gamma
        )
        return select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors)
    elif algo == 0:
        alternative_paths = compute_efficient_paths(G, current_node, exits, gamma, sort_paths=True)
        return select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors)


def compute_high_Knowledge_alternative_path(exits, risk_per_node, current_node, agent_group, G, gamma, risk_threshold):
    """
    Computes an alternative path for a high-knowledge agent group when the current path contains nodes
    with risk values at or above a given threshold. It evaluates the risk of the current path and, if necessary,
    computes alternative paths using either centrality measures or efficient paths, selecting the path with
    the lowest total risk (excluding the first and last nodes).

    Args:
        exits (list): List of exits.exits (list): List of exits.
        risk_per_node (dict): Mapping of nodes to their risk values.
        current_node: The node from which alternative paths are evaluated.
        agent_group (AgentGroup): An AgentGroup instance containing:
            - algorithm (int): Identifier for the algorithm (e.g., 0 for efficient paths, 1 for centrality measures).
            - path (list): The current path (list of nodes) followed by the agent group.
        G (networkx.Graph): The graph representing the simulation environment.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * global_min_cost are considered efficient.
        risk_threshold (float): The risk threshold above which a node is considered dangerous.

    Returns:
        list or None: The best alternative path (as a list of nodes) with lower total risk, or None if
                      no dangerous nodes are found in the current path.
    """
    # Retrieve the algorithm identifier and current path from the agent group.
    algo = agent_group.algorithm
    current_path = agent_group.path
    dangerous_path = False  # Flag to indicate if any node in the current path is dangerous.
    if current_path is not None:
        # Iterate over the nodes in the current path.
        for i, node in enumerate(current_path):
            # Check if the node's risk meets or exceeds the threshold.
            if risk_per_node.get(node, 0) >= risk_threshold:
                # If the node is the first node, skip it as there's no previous node to update from.
                if i == 0:
                    continue
                dangerous_path = True
    else:
        # A path is needed
        dangerous_path = True

    # If a dangerous node is found in the current path, attempt to compute an alternative path.
    if dangerous_path:
        if current_path is not None:
            # Update the graph with the current risk values for each node.
            update_graph_risks(G, risk_per_node)


        # Depending on the algorithm specified in the agent group, compute alternative paths.
        if algo == 1:
            # Use centralityMeasuresAlgorithm to compute alternative paths based on node centrality.
            _, _, alternative_paths = centralityMeasuresAlgorithm(
                G, current_node, exits, gamma
            )
        elif algo == 0:
            # Use compute_efficient_paths to compute alternative efficient paths.
            alternative_paths = compute_efficient_paths(
                G, current_node, exits, gamma
            )

        best_risk = float('inf')  # Initialize the best (lowest) risk value.

        # Iterate over the computed alternative paths to find the one with the lowest total risk.
        for path in alternative_paths:
            # Calculate the total risk for intermediate nodes (exclude first and last nodes).
            path_risk = sum(G.nodes[node]["risk"] for node in path[1:-1])
            # If this path has a lower risk than the current best, update best_risk and best_path.
            if path_risk < best_risk:
                best_risk = path_risk
                best_path = path
    else:
        # If no dangerous node is found in the current path, no alternative path is needed.
        return None

    # Return the alternative path with the lowest computed risk.
    return best_path

def compute_alternative_path(exits, agent_group, G, current_node=None, next_node=None, risk_per_node=None, risk_threshold=0.5):
    gamma = 0.4
    if agent_group.knowledge_level == 0:
        # Inside update_group_paths, after computing current_node and next_node
        return compute_low_Knowledge_alternative_path(
            exits,
            risk_per_node,
            next_node,
            current_node,
            agent_group,
            G,
            gamma,
            risk_threshold,
        )
    elif agent_group.knowledge_level == 1:
        return compute_high_Knowledge_alternative_path(
            exits,
            risk_per_node,
            current_node,
            agent_group,
            G,
            gamma,
            risk_threshold,
        )

def is_sublist(sub, main):
    """
    Checks if 'sub' is a contiguous sublist of 'main'.

    Args:
        sub (list): The potential sublist.
        main (list): The list in which to check for the sublist.

    Returns:
        bool: True if 'sub' is a contiguous sublist of 'main', False otherwise.
    """
    n = len(sub)
    for i in range(len(main) - n + 1):
        if main[i:i+n] == sub:
            return True
    return False

