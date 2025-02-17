
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

def handle_blocked_node_in_path(best_path, agent_group):
    """
    Checks if the best_path contains any blocked node from agent_group.blocked_nodes.
    If a blocked node is found, sets agent_group.wait_until_node to that blocked node.
    Additionally, if the node preceding the blocked node exists in best_path, it is added
    to agent_group.blocked_nodes to prevent backtracking.

    Parameters:
        best_path (list): The computed best alternative path as a list of nodes.
        agent_group: The agent group object that contains properties such as `blocked_nodes`
                     and `wait_until_node`.

    Returns:
        None
    """
    # Check if best_path is not empty and if any blocked node is present in best_path
    if best_path and any(node in best_path for node in agent_group.blocked_nodes):
        # Find the first blocked node that is in best_path
        blocked_node = next(node for node in agent_group.blocked_nodes if node in best_path)
        # Set the wait_until_node to the found blocked node
        agent_group.wait_until_node = blocked_node

        # Find the index of the blocked_node in best_path
        index = best_path.index(blocked_node)
        # If there is a node before the blocked_node in best_path, add it to blocked_nodes
        if index > 0:
            previous_node = best_path[index - 1]
            # Add the previous_node to agent_group.blocked_nodes if it's not already there
            if previous_node not in agent_group.blocked_nodes:
                agent_group.blocked_nodes.append(previous_node)

def select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group):
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
        agent_group (AgentGroup): An instance of AgentGroup containing:
            - agents (list): List of agent IDs.
            - path (list): Designated path for the group.
            - current_node (str): Identifier of the current node.
            - algorithm (int): Identifier for the algorithm used (e.g., 0 for shortest path, 1 for centrality measures).
            - knowledge_level (int): The knowledge level of the agents (0 or 1).
            - blocked_nodes (list, optional): List of nodes initially marked as blocked.
            - wait_until_node (str, optional): Node identifier where execution is paused until current_node matches it.

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

    handle_blocked_node_in_path(best_path, agent_group)

    return best_path
def compute_low_Knowledge_alternative_path(exits, risk_per_node, next_node, current_node, agent_group, G, gamma, risk_threshold):
    """
    Computes an alternative path based on node risk values and the selected algorithm.
    If the risk of the next node is below the threshold, no update is needed and None is returned.

    Parameters:
        exits (list): List of exit nodes.
        risk_per_node (dict): Mapping of each node to its risk value.
        next_node: The node following the current node in the current path.
        current_node: The current node in the path.
        agent_group (AgentGroup): An instance of AgentGroup containing:
            - agents (list): List of agent IDs.
            - path (list): Designated path for the group.
            - current_node (str): Identifier of the current node.
            - algorithm (int): Identifier for the algorithm used (e.g., 0 for shortest path, 1 for centrality measures).
            - knowledge_level (int): The knowledge level of the agents (0 or 1).
            - blocked_nodes (list, optional): List of nodes initially marked as blocked.
            - wait_until_node (str, optional): Node identifier where execution is paused until current_node matches it.
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

    ## If a current path is provided, remove its starting node from the neighbors (if applicable).
    ## to prevent going backwards
    #if current_path is not None and len(current_path) > 0:
    #    previous_node = current_path[0]
    #    if current_node != previous_node and previous_node in neighbors_sorted:
    #        neighbors_sorted.remove(previous_node)

    for neighbour in neighbors_sorted:
        if risk_per_node[neighbour] >= risk_threshold and neighbour not in agent_group.blocked_nodes:
            agent_group.blocked_nodes.append(neighbour)
            G.nodes[neighbour]['blocked'] = True

    # Determine the minimum risk among the neighbors.
    min_risk = G.nodes[neighbors_sorted[0]].get('risk', float('inf'))
    # Filter neighbors that have the same (lowest) risk or have a safe risk value.
    min_risk_neighbors = [n for n in neighbors_sorted if G.nodes[n].get('risk', float('inf')) == min_risk or G.nodes[n].get('risk', float('inf')) < risk_threshold]

    if algo == 1:

        # Get alternative paths using the centralityMeasuresAlgorithm.
        _, _, alternative_paths = centralityMeasuresAlgorithm(
            G, current_node, exits, gamma
        )
        return select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group)
    elif algo == 0:
        #not get_shortest_path because the blocked nodes need to be taken into account
        #alternative_paths = get_shortest_path(G, current_node, exits)
        alternative_paths = compute_efficient_paths(G, current_node, exits, gamma, True)
        return select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group)


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
    """
    Computes an alternative evacuation path for the agent group based on its knowledge level and risk assessment.

    The function temporarily marks nodes specified in the agent group's `blocked_nodes` as blocked in the graph.
    Depending on the group's knowledge level, it calls either the low-knowledge or high-knowledge alternative path
    computation function with a fixed gamma value. Finally, it resets the blocked status of all nodes and returns the best path.

    Parameters:
        exits: The list of exit nodes.
        agent_group: The agent group object containing properties such as blocked_nodes, wait_until_node, and knowledge_level.
        G (networkx.Graph or nx.DiGraph): The graph representing the environment.
        current_node: The current node where the agent group is located.
        next_node: The next planned node (used in low-knowledge alternative path computation).
        risk_per_node: The risk value associated with each node.
        risk_threshold (float): The risk threshold value to consider when computing the alternative path.

    Returns:
        best_path: The computed best alternative path as a list of nodes, or None if no alternative path is computed.
    """
    gamma = 0.2

    # Temporarily mark nodes in agent_group.blocked_nodes as blocked in the graph G.
    for node in agent_group.blocked_nodes:
        G.nodes[node]['blocked'] = True

    best_path = None
    try:
        # Check if there is no wait condition or if the wait condition is satisfied.
        if agent_group.wait_until_node is None or agent_group.current_node == agent_group.wait_until_node:
            # If the current node matches wait_until_node, reset wait_until_node to None.
            if agent_group.current_node == agent_group.wait_until_node:
                agent_group.wait_until_node = None

            # Compute the alternative path based on the agent group's knowledge level.
            if agent_group.knowledge_level == 0:
                best_path = compute_low_Knowledge_alternative_path(
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
                best_path = compute_high_Knowledge_alternative_path(
                    exits,
                    risk_per_node,
                    current_node,
                    agent_group,
                    G,
                    gamma,
                    risk_threshold,
                )
            else:
                # For unexpected knowledge levels, no alternative path is computed.
                best_path = None
        else:
            # If the wait condition is not satisfied, no alternative path is computed.
            best_path = None
    finally:
        # Unblock all nodes in the graph regardless of the outcome.
        for node in G.nodes():
            G.nodes[node]['blocked'] = False

    return best_path


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

