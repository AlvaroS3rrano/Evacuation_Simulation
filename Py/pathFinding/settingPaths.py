from Py.pathFinding.pathAlgorithms import *
from Py.database.paths_db_manager import *
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
            - awareness_level (int): The awareness level of the agents (0 or 1).
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

            # Remove candidate neighbors from neighbors_sorted to avoid reconsidering them if a path could not be found.
            if not best_path:
                for candidate in min_risk_neighbors:
                    if candidate in neighbors_sorted:
                        neighbors_sorted.remove(candidate)

        # If no best_path has been found yet, iterate through the sorted neighbors or min_risk_neighbors == 1.
        if best_path is None:
            for neighbor in neighbors_sorted:
                for path in alternative_paths:
                    if len(path) > 1 and path[1] == neighbor:
                        best_path = path
                        break
                if best_path:
                    break

    handle_blocked_node_in_path(best_path, agent_group)

    return best_path
def getAlternativePathsForNode(current_node, targets, gamma, currentG, paths_connection, *, blocked_nodes=None):
    """ Get alternative paths for a given node based on the specified algorithm and fetch from DB """

    # Convert dict_keys to a list if targets is a dict_keys object (do this only once before looping)
    if blocked_nodes is None:
        blocked_nodes = []
    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    all_paths = []

    # Process each target individually
    for target in targets:
        # Construct query to check if the path exists in the DB
        query = """
        SELECT * FROM paths
        WHERE source = ? AND target = ?
        """
        params = [current_node, target]

        # Fetch the paths from the database
        paths_df = pd.read_sql_query(query, paths_connection, params=params)

        # If paths are found in the database, add them to the result
        if not paths_df.empty:
            all_paths.extend([(json.loads(path), cost, betweenness) for path, cost, betweenness in zip(paths_df['path'], paths_df['cost'], paths_df['betweenness'])])
        else:
            # If paths are not found in the DB, compute them using collect_all_paths
            alternative_paths = collect_all_paths(currentG, current_node, [target])

            # Insert the newly computed paths into the DB
            for path, cost, betweenness in alternative_paths:
                insert_path(paths_connection, current_node, target, cost, path, betweenness)

            all_paths.extend(alternative_paths)  # Add the newly computed paths to the list

    # Filter out paths with blocked nodes
    paths_aux = collect_unblocked_paths(all_paths, blocked_nodes)
    if paths_aux:
      all_paths = paths_aux
    # Compute efficient paths based on cost
    efficient_paths = compute_efficient_paths(all_paths, gamma)

    return efficient_paths



def updateFloorPaths(EnvInf, current_floor, sources, targets, gamma, *, blocked_nodes=None):
    """ Update floor paths for a given floor with the calculated paths """
    if blocked_nodes is None:
        blocked_nodes = []
    all_next_floor_paths = {}
    nextG = EnvInf.floors[current_floor]
    for source in sources:
        alternative_paths = getAlternativePathsForNode(source, targets, gamma, nextG, EnvInf.paths_connection, blocked_nodes=blocked_nodes)
        all_next_floor_paths[source] = alternative_paths
    EnvInf.floor_paths[current_floor] = all_next_floor_paths


def getTargetsForCurrentNode(EnvInf, current_node, current_floor, exits):
    """ Determine the targets for the current node based on the floor and configuration """
    targets = exits
    if EnvInf.floor_number > 1:
        if current_floor != 0:
            next_floor = current_floor - 1
            if current_node not in EnvInf.floor_connecting_nodes[(current_floor, next_floor)]:
                targets = EnvInf.floor_connecting_nodes[(current_floor, next_floor)]
            else:
                targets = EnvInf.floor_connecting_nodes[(next_floor, next_floor - 1)]
    return targets


def getPosiblePaths(EnvInf, current_node, exits, gamma, algo, *, blocked_nodes=None):
    if blocked_nodes is None:
        blocked_nodes = []
    alternative_paths = []
    current_floor = EnvInf.graph.nodes[current_node]["floor"]

    # Update paths for previous floors
    for i in range(current_floor):
        if i not in EnvInf.floor_paths:
            sources = EnvInf.floor_connecting_nodes[(i+1, i)]
            targets = exits if i == 0 else EnvInf.floor_connecting_nodes[(i, i-1)]
            updateFloorPaths(EnvInf, i, sources, targets, gamma, blocked_nodes=blocked_nodes)

    # Get the paths for the current floor if not available
    if current_floor not in EnvInf.floor_paths:
        EnvInf.floor_paths[current_floor] = {}
    if current_node not in EnvInf.floor_paths[current_floor]:
        targets = getTargetsForCurrentNode(EnvInf, current_node, current_floor, exits)
        currentG = EnvInf.graph if EnvInf.floors == None else EnvInf.floors[current_floor]
        alternative_paths = getAlternativePathsForNode(current_node, targets, gamma, currentG, EnvInf.paths_connection, blocked_nodes=blocked_nodes)
        EnvInf.floor_paths[current_floor][current_node] = alternative_paths
    else:
        alternative_paths = EnvInf.floor_paths[current_floor][current_node]

    # Combine previous floor paths with the current floor paths
    alternative_paths_aux = []
    for i in range(current_floor):
        for first_segment, first_cost, first_betweeness in alternative_paths:
            for node, segments in EnvInf.floor_paths[i].items():
                if first_segment[-1] == node:
                    for second_segment, second_cost, second_betweeness in segments:
                        complete_path = first_segment + second_segment[1:]
                        complete_path_cost = first_cost + second_cost
                        complete_path_betweeness = first_betweeness + second_betweeness
                        alternative_paths_aux.append((complete_path, complete_path_cost, complete_path_betweeness))
        alternative_paths = alternative_paths_aux

    # Sort paths based on the algorithm
    if algo == 0: # based on cost
        alternative_paths.sort(key=lambda x: x[1])
    elif algo == 1: # based on betweenness
        alternative_paths.sort(key=lambda x: x[2], reverse=True)

    # Return only the paths, without the costs
    paths = [path for path, _, _ in alternative_paths]
    return paths


def compute_low_awareness_alternative_path(exits, risk_per_node, next_node, current_node, agent_group, EnvInf, gamma, risk_threshold):
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
            - awareness_level (int): The awareness level of the agents (0 or 1).
            - blocked_nodes (list, optional): List of nodes initially marked as blocked.
            - wait_until_node (str, optional): Node identifier where execution is paused until current_node matches it.
        EnvInf (Environment_info): An instance of the Environment_info class, which includes the graph and environment details.
                                   It provides access to the environment's graph and floor-specific data.
        gamma (float): Tolerance factor for path cost. Only paths with a total cost less than or equal to
                       (1 + gamma) * global_min_cost are considered efficient.
        risk_threshold (float): Threshold above which a node is considered unsafe.

    Returns:
        list or None: The best alternative path if one is found, or None if no update is needed or found.
    """

    algo = agent_group.algorithm
    current_path = getattr(agent_group, 'path', None)
    G = EnvInf.graph

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

    # Block the riskier neighbouring nodes
    for neighbour in neighbors_sorted:
        if risk_per_node[neighbour] >= risk_threshold and neighbour not in agent_group.blocked_nodes:
            agent_group.blocked_nodes.append(neighbour)

    # Determine the minimum risk among the neighbors.
    min_risk = G.nodes[neighbors_sorted[0]].get('risk', float('inf'))
    # Filter neighbors that have the same (lowest) risk or have a safe risk value.
    min_risk_neighbors = [n for n in neighbors_sorted if G.nodes[n].get('risk', float('inf')) == min_risk or G.nodes[n].get('risk', float('inf')) < risk_threshold]

    alternative_paths = getPosiblePaths(EnvInf, current_node, exits, gamma, algo, blocked_nodes=agent_group.blocked_nodes)
    return select_best_alternative_path(alternative_paths, neighbors_sorted, min_risk_neighbors, agent_group)


def compute_high_awareness_alternative_path(exits, risk_per_node, current_node, agent_group, EnvInf, gamma, risk_threshold):
    """
    Computes an alternative path for a high-awareness agent group when the current path contains nodes
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
        EnvInf (Environment_info): An instance of the Environment_info class, which includes the graph and environment details.
                                   It provides access to the environment's graph and floor-specific data.
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
    G = EnvInf.graph
    dangerous_path = False  # Flag to indicate if any node in the current path is dangerous.
    if current_path is not None:
        # Iterate over the nodes in the current path.
        try:
            index = current_path.index(current_node)
            for node in current_path[index + 1:]:
                risk = risk_per_node.get(node, 0.0)
                if risk >= risk_threshold:
                    if node not in agent_group.blocked_nodes:
                        agent_group.blocked_nodes.append(node)
                    dangerous_path = True
        except ValueError:
            print(f"Error checking the risk of the paths in compute_high_awareness_alternative_path")
    else:
        # A path is needed
        dangerous_path = True

    # If a dangerous node is found in the current path, attempt to compute an alternative path.
    if dangerous_path:
        # Update the graph with the current risk values for each node.
        update_graph_risks(G, risk_per_node)


        alternative_paths = getPosiblePaths(EnvInf, current_node, exits, gamma, algo, blocked_nodes=agent_group.blocked_nodes)

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


def compute_alternative_path(exits, agent_group, EnvInf, current_node=None, next_node=None, risk_per_node=None,
                             risk_threshold=0.5, gamma=0.4):
    """
    Computes an alternative evacuation path for the agent group based on its awareness level and risk assessment.

    The function temporarily marks nodes specified in the agent group's `blocked_nodes` as blocked in the graph.
    Depending on the group's awareness level, it calls either the low-awareness or high-awareness alternative path
    computation function using a fixed gamma value. Finally, it resets the blocked status of all nodes and returns
    the best path found.

    Parameters:
        exits: The list of exit nodes.
        agent_group: The agent group object containing properties such as blocked_nodes, wait_until_node, and awareness_level.
        EnvInf (Environment_info): An instance of the Environment_info class, which includes the graph and environment details.
                                   It provides access to the environment's graph and floor-specific data.
        current_node: The current node where the agent group is located.
        next_node: The next planned node (used in low-awareness alternative path computation).
        risk_per_node: The risk value associated with each node.
        risk_threshold (float): The risk threshold value to consider when computing the alternative path.
        gamma (float): A weighting parameter that influences the alternative path computation by controlling the
                       trade-off between risk minimization and path optimality.

    Returns:
        best_path: The computed best alternative path as a list of nodes, or None if no alternative path is computed.
    """
    # Use a local variable for clarity.
    wait_node = agent_group.wait_until_node

    # If there is no wait condition, or if any agent is at the wait node, clear the condition.
    if wait_node is None or (agent_group.current_nodes and wait_node in agent_group.current_nodes.values()):
        agent_group.wait_until_node = None

        # Compute the alternative path based on the agent group's awareness level.
        if agent_group.awareness_level == 0:
            best_path = compute_low_awareness_alternative_path(
                exits,
                risk_per_node,
                next_node,
                current_node,
                agent_group,
                EnvInf,
                gamma,
                risk_threshold,
            )
        elif agent_group.awareness_level == 1:
            best_path = compute_high_awareness_alternative_path(
                exits,
                risk_per_node,
                current_node,
                agent_group,
                EnvInf,
                gamma,
                risk_threshold,
            )
        else:
            best_path = None
    else:
        best_path = None

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

