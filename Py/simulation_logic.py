from jupedsim.internal.notebook_utils import read_sqlite_file

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
    current_path = agent_group.floor_path
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

def get_stairs_agents(prev_floor_key, mode, floor_simulation_data, G):
    """
    Retrieve agents from the simulation on the previous floor (i.e., the lower floor)
    who ended their trajectory at a stairs node, and determine the corresponding node
    on the next (higher) floor that they will transition to.

    Parameters:
        prev_floor_key (numeric): The key of the previous (lower) floor.
        mode (str): The simulation mode used to access trajectory data.
        floor_simulation_data (dict): Global dictionary containing simulation data for each floor.
        G (networkx.Graph): Graph containing nodes with attributes such as 'is_stairs' and 'floor'.

    Returns:
        dict: A dictionary mapping agent IDs to a dictionary with the following keys:
              - 'position': A tuple (x, y) representing the agent's position when reaching the stairs.
              - 'frame': The simulation frame at which the agent reached the stairs.
              - 'current_node': The node on the higher floor connected to the stairs.
              - 'source': The node the agent group started at.
    """
    stairs_agents = {}

    # Retrieve the trajectory file for the previous floor and read its data.
    prev_trajectory_file = floor_simulation_data[prev_floor_key]["trajectory_files"][mode]
    trajectory_data, _ = read_sqlite_file(prev_trajectory_file)
    df = trajectory_data.data

    # Get the last frame for each agent.
    last_frames = df.loc[df.groupby("id")["frame"].idxmax()].reset_index(drop=True)

    # Get agent groups for the previous floor and simulation mode.
    prev_agent_groups = floor_simulation_data[prev_floor_key]["agent_groups_per_mode"][mode]

    for source, agent_group in prev_agent_groups.items():
        # Determine the last node in the agent group's floor_path.
        last_node = agent_group.floor_path[-1]
        # If the last node is a stairs node, process the agents.
        if G.nodes[last_node].get("is_stairs", False):
            # Calculate the current (lower) floor based on the previous floor key.
            current_floor = prev_floor_key - 1
            node_in_new_floor = ""
            # Identify the neighbor of the stairs node that belongs to the higher floor.
            for neighbour in G.neighbors(last_node):
                if G.nodes[neighbour]["floor"] == current_floor:
                    node_in_new_floor = neighbour
                    break

            # Create the entry for this source if it doesn't exist.
            if source not in stairs_agents:
                stairs_agents[source] = {
                    "current_node": node_in_new_floor,
                    "agents": {}
                }

            # For each agent in the group, record their position and frame.
            for agent in agent_group.agents:
                agent_frame_row = last_frames[last_frames["id"] == agent]
                if not agent_frame_row.empty:
                    pos = (agent_frame_row.iloc[0]["x"], agent_frame_row.iloc[0]["y"])
                    frame_reached = agent_frame_row.iloc[0]["frame"]
                    stairs_agents[source]["agents"][agent] = {
                        "position": pos,
                        "frame": frame_reached
                    }

    return stairs_agents



