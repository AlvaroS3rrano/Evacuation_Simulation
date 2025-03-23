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


def update_agent_speed_on_stairs(G, simulation_config, agent_group):
    """
    Checks each agent's current node and, if that node is a staircase, changes the agent's speed
    to stairs_max_speed until they leave the staircase node.

    Args:
        G: G (networkx.DiGraph): A directed graph where nodes have a 'is_stairs' attribute.
        simulation_config: An object containing simulation configuration, including:
                           - simulation: the simulation object (assumed to have the graph in simulation.G),
                           - normal_max_speed: the normal speed for agents,
                           - stairs_max_speed: the speed for agents on stairs.
        agent_group: An object that contains the group of agents, with:
                     - agents: list of agent IDs,
                     - current_nodes: a dictionary mapping each agent ID to its current node.
    """
    simulation = simulation_config.simulation

    for agent_id in agent_group.agents:
        if not any(agent.id == agent_id for agent in simulation.agents()):
            continue
        # Retrieve the agent object
        agent = simulation.agent(agent_id)
        # Get the current node for the agent from the group
        current_node = agent_group.current_nodes.get(agent_id)

        if current_node is not None:
            # Check if the current node is marked as a staircase; default to False if not set
            is_stairs = G.nodes[current_node].get('is_stairs', False)
            if is_stairs:
                # Set the agent's speed to stairs_max_speed when on a staircase
                agent.model.v0 = simulation_config.stairs_max_speed
            else:
                # Otherwise, use the normal maximum speed
                agent.model.v0 = simulation_config.normal_max_speed
        else:
            # If the current node is undefined, default to normal speed
            agent.model.v0 = simulation_config.normal_max_speed


def transform_position(old_pos, old_area, new_area):
    """
    Transforms the position of an agent from the original area to the equivalent position in a new area.

    Assumes that the new area is the same size and shape as the original area.

    Args:
        old_pos (tuple): The (x, y) position of the agent in the original area.
        old_area (Polygon): The original area (as a shapely Polygon).
        new_area (Polygon): The new area (as a shapely Polygon) where the agent will be transported.

    Returns:
        tuple: The (x, y) position in the new area equivalent to old_pos.
    """
    # Get the bounding boxes for both areas: (minx, miny, maxx, maxy)
    old_minx, old_miny, old_maxx, old_maxy = old_area.bounds
    new_minx, new_miny, new_maxx, new_maxy = new_area.bounds

    # Calculate the relative position within the original area.
    rel_x = (old_pos[0] - old_minx) / (old_maxx - old_minx)
    rel_y = (old_pos[1] - old_miny) / (old_maxy - old_miny)

    # Map the relative position to the new area.
    new_x = new_minx + rel_x * (new_maxx - new_minx)
    new_y = new_miny + rel_y * (new_maxy - new_miny)

    return (new_x, new_y)