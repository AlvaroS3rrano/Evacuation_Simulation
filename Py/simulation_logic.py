def compute_current_nodes(simulation_config, agent_group, frame) -> None:
    """
    Computes the current node for each agent in the agent_group based on their individual stage,
    and stores the results in agent_group.current_nodes.

    For each agent in the group, this function:
      - Retrieves the agent's current stage (agent.stage_id).
      - Finds the corresponding node from simulation_config.waypoints_ids or exit_ids.
      - Determines the agent's current node as the node immediately preceding the found node in the group's path.

    Args:
        simulation_config: An object that includes:
            - simulation: The simulation object which manages agents (accessible via simulation.agents() and simulation.agent(id)).
            - waypoints_ids (dict): Mapping from graph nodes to simulation stage IDs.
            - exit_ids (dict): Mapping from exit nodes.
        agent_group: An object with the following attributes:
            - agents (list): List representing agent IDs.
            - path (list): List representing the group's current path (ordered list of nodes).
            - current_nodes (dict): Dictionary mapping agent IDs to their current nodes (to be updated).
        frame: The current frame (not used directly in computation here).
    """
    simulation = simulation_config.simulation
    waypoints_ids = simulation_config.waypoints_ids
    exit_ids = simulation_config.exit_ids
    current_path = agent_group.path
    computed_current_nodes = {}

    for agent_id in agent_group.agents:
        # Check if the agent exists in the simulation.
        if not any(agent.id == agent_id for agent in simulation.agents()):
            computed_current_nodes[agent_id] = current_path[-1]
            continue

        # Retrieve the agent and its current stage.
        agent = simulation.agent(agent_id)
        current_stage = agent.stage_id

        # Find the corresponding node in the waypoints_ids mapping.
        next_node = None
        for node, waypoint in waypoints_ids.items():
            if waypoint == current_stage:
                next_node = node
                break

        if not next_node:
            for node, exit_id in exit_ids.items():
                if exit_id == current_stage:
                    next_node = node
                    break

        if not next_node:
            # No corresponding node found.
            computed_current_nodes[agent_id] = current_path[-1]
            continue

        # Find the index of next_node in the group's path.
        try:
            node_index = current_path.index(next_node)
        except ValueError:
            # next_node is not in the current path.
            computed_current_nodes[agent_id] = None
            continue

        # If next_node is the first element, there's no previous node.
        if node_index == 0:
            computed_current_nodes[agent_id] = None
        else:
            computed_current_nodes[agent_id] = current_path[node_index - 1]

    # Store the computed current nodes in the agent_group.
    agent_group.current_nodes = computed_current_nodes
