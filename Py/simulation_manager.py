import jupedsim as jps

from Py.classes.agentGroup import AgentGroup
from Py.database.danger_sim_db_manager import get_risk_levels_by_frame
from Py.pathFinding.settingPaths import *
from Py.journey_configuration import set_journeys
from Py.database.agent_area_db_manager import *
from Py.simulation_logic import compute_current_nodes, update_agent_speed_on_stairs, get_stairs_agents
from Notebooks.Main.polygons.environmnet import get_floor_segment
def update_group_paths(simulation_config, risk_per_node, agent_group, G, risk_threshold=0.5):
    """
    Updates the group's path based on the current status of each agent using the provided current_nodes mapping.

    The process is as follows:
      1. Verify that the agents_ids list exists.
      2. Depending on the awareness_level:
           - If it is 1, only the first agent of the group is evaluated.
           - Otherwise, all agents are evaluated.
      3. For each selected agent, using its current node (from current_nodes), determine the next node
         in the current path. Then, check if the path needs to be changed.
         If for any agent a change is needed, update the path for the entire group,
         stop further checks, and return the updated agent_group.

    Args:
        simulation_config (SimulationConfig): Contains:
            - simulation: Object that manages the simulation (agents and environment).
            - every_nth_frame (int): Interval at which agent paths are updated.
            - waypoints_ids (dict): Mapping from graph nodes to simulation waypoint IDs.
            - journeys_ids (dict): Mapping of journey identifiers to tuples (journey_id, path).
        risk_per_node (dict): Mapping of each node to its risk value.
        agent_group (AgentGroup): An AgentGroup instance containing:
            - agents (list): List of agent IDs.
            - path (list): List representing the group's current path.
            - algorithm (int): Identifier for the algorithm used.
            - awareness_level (int): The awareness level of the agents.
            - current_node: The current node (to be updated if changed).
        G: Graph or structure used for computing alternative paths.
        current_nodes (dict): A dictionary where keys are agent IDs and values are the agent's current node.
        risk_threshold (float): Threshold above which a path segment is considered unsafe.

    Returns:
        AgentGroup: The updated AgentGroup with the new path if a change was made,
                    or the original AgentGroup if no update occurred.
    """
    agents_ids = agent_group.agents

    # First, check that agents_ids exists.
    if not agents_ids:
        return agent_group

    current_path = agent_group.path
    current_nodes = agent_group.current_nodes
    simulation = simulation_config.simulation
    waypoints_ids = simulation_config.waypoints_ids

    # Select the list of agents to evaluate:
    # If awareness_level is 1, only evaluate the first agent.
    if agent_group.awareness_level == 1:
        agents_to_check = [agents_ids[0]]
        exits = simulation_config.environment.environment_exits
    else:
        agents_to_check = agents_ids
        exits = simulation_config.get_exit_ids_keys()

    for agent_id in agents_to_check:
        # Verify that the agent exists in the simulation.
        agent_exists = any(agent.id == agent_id for agent in simulation.agents())
        if not agent_exists:
            return agent_group  # If any agent doesn't exist, return the original group.

        # Ensure the current node is provided in current_nodes.
        if agent_id not in current_nodes:
            return agent_group

        # Get the current node from the dictionary.
        current_node = current_nodes[agent_id]

        # Attempt to obtain the index of the current node in the current path.
        try:
            node_index = current_path.index(current_node)
        except ValueError:
            return agent_group

        # If the current node is the last node in the path, no update is needed.
        if node_index == len(current_path) - 1:
            continue

        # The next node in the path is the one immediately after the current node.
        next_node = current_path[node_index + 1]


        # Calculate an alternative path from the current_node to the next_node.
        best_path = compute_alternative_path(
            exits,
            agent_group, G,
            current_node, next_node,
            risk_per_node, risk_threshold,
            simulation_config.gamma
        )

        # If a valid alternative path is found and it is different from the current path...
        if best_path is not None and not is_sublist(best_path, current_path):
            agent_group.path = best_path
            if agent_group.awareness_level == 1:
                best_path = get_floor_segment(best_path, simulation_config.environment, agent_group.current_floor)
            journeys_ids = set_journeys(
                simulation, current_node,
                [best_path],
                waypoints_ids, simulation_config.exit_ids
            )
            # Assume best_path has at least two nodes.
            new_next_node = best_path[1]
            next_stage_id = waypoints_ids[new_next_node]
            new_journey_id, _ = journeys_ids[current_node][0]

            # Update the journey for ALL agents in the group.
            for agent_id in agents_ids:
                simulation.switch_agent_journey(agent_id, new_journey_id, next_stage_id)

            agent_group.floor_path = best_path

            # Return the updated agent group with the new path.
            return agent_group

    # If no update was made, return the original agent_group.
    return agent_group

def run_agent_simulation(simulation_config, agent_groups, G, connection, agent_area_connection, transition_data, risk_threshold):
    """
    Runs the agent simulation, updating agent paths based on current risk levels retrieved from the database.

    Args:
        simulation_config (SimulationConfig): An instance of SimulationConfig containing:
            - simulation: The simulation object managing agents and the environment.
            - every_nth_frame_simulation (int): The interval at which agent paths are updated.
            - every_nth_frame_animation (int): The interval at which animations (or other updates) are applied.
            - waypoints_ids (dict): Mapping of graph node IDs to simulation waypoint IDs.
            - stairs_max_speed (float): The maximum speed for agents on stairs.
        agent_groups (dict): Mapping of starting nodes to AgentGroups.
        G (networkx.Graph): Global graph containing the nodes and edges of the environment.
        connection (sqlite3.Connection): Active SQLite connection to retrieve risk levels.
        agent_area_connection: Connection or handler to write agent area data.
        transition_data (dict): A dictionary mapping frame numbers to transition information.
            Expected structure: { frame: {"position": ..., "journey_id": ..., "first_waypoint_id": ..., ...}, ... }
        risk_threshold (float): The risk level threshold above which agents will attempt to avoid high-risk areas.
    """
    while simulation_config.simulation.agent_count() > 0 or transition_data is not None:
        # Advance the simulation by one frame
        simulation_config.simulation.iterate()
        iteration = simulation_config.simulation.iteration_count()

        every_nth_frame_simulation = simulation_config.every_nth_frame_simulation
        every_nth_frame_animation = simulation_config.every_nth_frame_animation

        if iteration % every_nth_frame_simulation == 0:
            frame = iteration / every_nth_frame_simulation

            if transition_data:
                # We create a list of keys to remove to avoid modifying the dict during iteration.
                frames_to_remove = []
                for agent_frame, values in transition_data.items():
                    if agent_frame == frame:
                        # Use values from the corresponding transition data entry.
                        agent = set_agent_in_simulation(
                            simulation_config.simulation,
                            values["position"],
                            values["journey_id"],
                            values["first_waypoint_id"],
                            simulation_config.stairs_max_speed
                        )
                        # Optionally, you could add the new agent to its corresponding agent group if needed.
                        frames_to_remove.append(agent_frame)
                # Remove processed entries
                for key in frames_to_remove:
                    transition_data.pop(key)

                if not transition_data:
                    transition_data = None


            # Update agent paths only at specified intervals
            if frame % every_nth_frame_animation == 0:
                try:
                    # Fetch risk levels for the current frame from the database
                    risks_this_frame = get_risk_levels_by_frame(connection, frame)

                    for key, agent_group in agent_groups.items():
                        # This first so that there are no confusions when the path is changed
                        compute_current_nodes(simulation_config, agent_group, frame)
                        # Write in which area the agents are in this frame
                        write_agent_area(agent_area_connection, frame, agent_group.agents, agent_group.current_nodes, risks_this_frame)

                        update_agent_speed_on_stairs(G, simulation_config, agent_group)

                        # Update paths for the agents based on current risks and threshold
                        agent_groups[key] = update_group_paths(
                            simulation_config, risks_this_frame, agent_group, G, risk_threshold=risk_threshold
                        )
                except Exception as e:
                    print(f"Error updating paths at frame {frame}: {e}")


def set_agent_in_simulation(simulation, position, journey_id, first_waypoint_id, speed):
    """
    Add a single agent to the simulation with the specified parameters.

    Parameters:
        simulation: The simulation object with an 'add_agent' method.
        position: The initial position of the agent.
        journey_id: The journey ID for the agent.
        first_waypoint_id: The starting waypoint (stage) for the agent.
        speed: The desired maximum speed for the agent.

    Returns:
        The created agent.
    """
    agent = simulation.add_agent(
        jps.CollisionFreeSpeedModelAgentParameters(
            position=position,        # Initial position of the agent.
            journey_id=journey_id,      # Journey ID for the agent.
            stage_id=first_waypoint_id, # Starting waypoint for the agent.
            v0=speed                  # Desired maximum speed of the agent.
        )
    )
    return agent

def set_agents_in_simulation(simulation, positions, journey_id, first_waypoint_id, speed):
    """
    Add multiple agents to the simulation.

    This function iterates over a list of positions, creates an agent for each
    position using the set_agent_in_simulation() function, and returns a list of agents.

    Parameters:
        simulation: The simulation object with an 'add_agent' method.
        positions (list): A list of positions where agents should be added.
        journey_id: The journey ID for each agent.
        first_waypoint_id: The starting waypoint (stage) for each agent.
        speed: The desired maximum speed for each agent.

    Returns:
        list: A list of created agents.
    """
    agents = []
    for position in positions:
        agent = set_agent_in_simulation(simulation, position, journey_id, first_waypoint_id, speed)
        agents.append(agent)
    return agents

def get_transition_path(idx, sorted_floor_keys, mode, floor_simulation_data, simulation_config,
                        awareness_levels_per_group, algorithm_per_group, connection):
    """
    Compute the transition information from the previous floor based on simulation data.

    If the current floor key (derived from idx) is greater than 0, the function:
      - Retrieves the previous floor key from the sorted list.
      - Obtains the agents that reached a stairs node on the previous floor (grouped by source).
      - For each source:
          * If the awareness level for the given mode is 1, it retrieves the long path from the
            corresponding agent group and extracts the relevant floor segment.
          * Otherwise, it creates an auxiliary AgentGroup, finds the minimum frame among the agents,
            rounds it to the nearest multiple defined by every_nth_frame_simulation, retrieves risk levels
            for that frame, and computes an alternative path based on those risk levels.
      - Sets up journey IDs and determines the first waypoint for the transition.
      - Then, for each agent in the stairs_agents data, it creates an entry mapping the frame at which
        the agent reached the stairs to a structure containing its position, the transition path,
        journey IDs, first waypoint ID, and the agent group (represented by the common current_node).

    Parameters:
        idx (int): Current index in the sorted_floor_keys list.
        sorted_floor_keys (list): Sorted list of floor keys.
        mode (str): Simulation mode identifier.
        floor_simulation_data (dict): Dictionary containing simulation data for each floor.
        simulation_config (object): Configuration object containing simulation parameters and environment details,
                                    including environment, gamma, every_nth_frame_simulation, simulation,
                                    waypoints_ids, and exit_ids.
        awareness_levels_per_group (dict): Mapping from simulation modes to awareness levels.
        algorithm_per_group (dict): Mapping from simulation modes to algorithms for each group.
        connection (sqlite3.Connection): Active SQLite connection to retrieve risk levels.

    Returns:
        dict: A dictionary mapping each agent's frame (when the agent reached the stairs) to a dictionary
              with the following keys:
                  - "position": Agent's position at the time of transition.
                  - "path": The computed transition path.
                  - "journey_ids": Journey IDs for the agent.
                  - "first_waypoint_id": The starting waypoint for the agent.
                  - "agent_group": The identifier (or data) of the agent group (common current_node).
              Returns None if idx is 0.
    """
    environment = simulation_config.environment
    current_floor_key = sorted_floor_keys[idx]
    floor = environment.floors[current_floor_key]
    gamma = simulation_config.gamma
    n = simulation_config.every_nth_frame_animation
    simulation = simulation_config.simulation

    if idx > 0:
        prev_floor_key = sorted_floor_keys[idx - 1]
        stairs_agents = get_stairs_agents(prev_floor_key, mode, floor_simulation_data, environment.graph)
        # This will hold the final transition data for each agent by frame.
        transition_data = {}

        if stairs_agents == {}:
            print(f"There were no agents that reached a stairs node.")

        # Process each source (agent group start) in the stairs agents data.
        for source, stairs_agents_values in stairs_agents.items():
            # Compute the transition path based on awareness level.
            if awareness_levels_per_group[mode] == 1:
                prev_floor_agent_groups_per_mode = floor_simulation_data[prev_floor_key]['agent_groups_per_mode']
                long_path = prev_floor_agent_groups_per_mode[mode][source].path
                path = get_floor_segment(long_path, environment, current_floor_key)
            else:
                # Create an auxiliary AgentGroup for further path computation.
                agent_group_aux = AgentGroup(
                    None, None, None, None,
                    algorithm_per_group[mode],
                    awareness_levels_per_group[mode],
                    current_floor_key
                )
                # Compute the closest frame (rounded to the nearest multiple of n) among the agents.
                min_frame = min(agent_info["frame"] for agent_info in stairs_agents_values["agents"].values())
                closest_divisible = round(min_frame / n) * n
                risk_earliest_frame = get_risk_levels_by_frame(connection, closest_divisible)
                path = compute_alternative_path(
                    floor.exit_polygons.keys(),
                    agent_group_aux,
                    floor.graph,
                    stairs_agents_values["current_node"],
                    risk_per_node=risk_earliest_frame,
                    gamma=gamma
                )

            journeys_ids = set_journeys(
                simulation,
                stairs_agents_values["current_node"],
                [path],
                simulation_config.waypoints_ids,
                simulation_config.exit_ids
            )

            journey_id, best_path_source = journeys_ids[stairs_agents_values["current_node"]][0]

            next_node = best_path_source[1]
            first_waypoint_id = simulation_config.waypoints_ids[next_node]

            # For each agent in this group, add an entry to transition_data.
            for agent, agent_info in stairs_agents_values["agents"].items():
                frame = agent_info["frame"]
                transition_data[frame] = {
                    "position": agent_info["position"],
                    "path": path,
                    "journey_id": journey_id,
                    "first_waypoint_id": first_waypoint_id,
                    "agent_group": stairs_agents_values["current_node"]
                }
        return transition_data
    else:
        return None



