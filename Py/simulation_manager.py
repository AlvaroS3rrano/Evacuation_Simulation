import jupedsim as jps

from Py.classes.agentGroup import AgentGroup
from Py.database.danger_sim_db_manager import get_risk_levels_by_frame
from Py.pathFinding.settingPaths import *
from Py.journey_configuration import set_journeys
from Py.database.agent_area_db_manager import *
from Py.simulation_logic import compute_current_nodes, update_agent_speed_on_stairs
def update_group_paths(simulation_config, risk_per_node, agent_group, EnvInf, risk_threshold=0.5):
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
         EnvInf (Environment_info): An instance of the Environment_info class, which includes the graph and environment details.
                                   It provides access to the environment's graph and floor-specific data.
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
    else:
        agents_to_check = agents_ids

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
            simulation_config.get_exit_ids_keys(),
            agent_group, EnvInf,
            current_node, next_node,
            risk_per_node, risk_threshold,
            simulation_config.gamma
        )

        # If a valid alternative path is found and it is different from the current path...
        if best_path is not None and not is_sublist(best_path, current_path):
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

            agent_group.path = best_path

            # Return the updated agent group with the new path.
            return agent_group

    # If no update was made, return the original agent_group.
    return agent_group


def run_agent_simulation(simulation_config, agent_groups, EnvInf, connection, agent_area_connection, risk_threshold):
    """
    Runs the agent simulation, updating agent paths based on current risk levels retrieved from the database.

    Args:
        simulation_config (SimulationConfig): An instance of SimulationConfig containing:
            - simulation: The simulation object managing agents and the environment.
            - every_nth_frame (int): The interval at which agent paths are updated.
            - waypoints_ids (dict): Mapping of graph node IDs to simulation waypoint IDs.
        agent_groups (dict): Mapping of starting nodes to AgentGroups.
        risk_threshold (float): The risk level threshold above which agents will attempt to avoid high-risk areas.
    """
    while simulation_config.simulation.agent_count() > 0:
        # Advance the simulation by one frame
        simulation_config.simulation.iterate()
        iteration = simulation_config.simulation.iteration_count()

        every_nth_frame_simulation = simulation_config.every_nth_frame_simulation
        every_nth_frame_animation = simulation_config.every_nth_frame_animation

        if iteration % every_nth_frame_simulation == 0:
            frame = iteration / every_nth_frame_simulation

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

                        update_agent_speed_on_stairs(EnvInf.graph, simulation_config, agent_group)

                        # Update paths for the agents based on current risks and threshold
                        agent_groups[key] = update_group_paths(
                            simulation_config, risks_this_frame, agent_group, EnvInf, risk_threshold=risk_threshold
                        )
                except Exception as e:
                    print(f"Error updating paths at frame {frame}: {e}")

def set_agents_in_simulation(simulation, positions, journey_id, first_waypoint_id, speed):
    agents = []
    for position in positions:  # Use the second half of the positions
        # Add agents with specified parameters (e.g., position, journey, velocity)
        agents.append(
            simulation.add_agent(
                jps.CollisionFreeSpeedModelAgentParameters(
                    position=position,       # Initial position of the agent
                    journey_id=journey_id,   # Journey ID for the agent
                    stage_id=first_waypoint_id,  # Starting waypoint for the agent
                    v0=speed, # Desired maximum speed of the agent
                )
            )
        )
    return agents
