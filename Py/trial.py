import pathlib

import jupedsim as jps
import matplotlib.pyplot as plt
import pedpy
import shapely
import sqlite3
from matplotlib.patches import Circle
from shapely import Polygon
import networkx as nx
from jupedsim.internal.notebook_utils import animate, read_sqlite_file
import plotly.graph_objects as go

# from Py.centralityMeasures import centralityMeasuresAlgorithm
from Py.riskSimulationValues import RiskSimulationValues
from Py.dangerSimulation import *
from Py.animation import animate
from Py.pathAlgorithms import get_sortest_path, centralityMeasuresAlgorithm, compute_efficient_paths, get_paths_with_distances
from Py.simulation_config import SimulationConfig
from Py.agentGroup import AgentGroup
from Py.settingPaths import *


complete_area = Polygon(
    [
        (0, -2),
        (0, 18),
        (32, 18),
        (32, -2),
    ]
)
obstacles = [
    #bottom
    Polygon([(0, -2), (14, -2), (14, 0),(0, 0)]),
    Polygon([(16, -2), (32, -2), (32, 0),(16, 0)]),

    #top
    Polygon([(0, 16), (14, 16), (14, 18),(0, 18)]),
    Polygon([(16, 16), (32, 16), (32, 18),(16, 18)]),

    Polygon([(2, 2), (14, 2), (14, 7), (2, 7)]),
    Polygon([(16, 2), (28, 2), (28, 7), (16, 7)]),
    Polygon([(2, 9), (14, 9), (14, 14), (2, 14)]),
    Polygon([(16, 9), (28, 9), (28, 14), (16, 14)]),

    Polygon([(30, 0), (32, 0), (32, 3.5), (30, 3.5)]),
    Polygon([(30, 5.5), (32, 5.5), (32, 10.5), (30, 10.5)]),
    Polygon([(30, 12.5), (32, 12.5), (32, 18), (30, 18)]),
]

exit_polygons = {'EA': [(14, 0), (14, -2), (16, -2), (16, 0)], 'EB':[(14, 16), (14, 18), (16, 18), (16, 16)], 'EC':[(30, 3.5), (32, 3.5), (32, 5.5), (30, 5.5)], 'ED':[(30, 10.5), (32, 10.5), (32, 12.5), (30, 12.5)]}

waypoints = {'A':([1, 11.5], 1), 'B':([1, 8], 1), 'C':([1, 4.5], 1), 'D':([1, 1], 1), 'E':([8, 1], 1), 'F':([15, 1], 1), 'G':([22, 1], 1), 'H':([29, 1], 1), 'I':([29, 4.5], 1), 'J':([29, 8], 1), 'K':([29, 11.5], 1), 'L':([29, 15], 1), 'M':([22, 15], 1), 'N':([15, 15], 1), 'O':([8, 15], 1), 'P':([1, 15], 1), 'Q':([8, 8], 1), 'R':([15, 8], 1), 'S':([22, 8], 1), 'T':([15, 11.5], 1), 'U':([15, 4.5], 1)}
distribution_polygons = {
    'A': Polygon([[0, 9], [2, 9], [2, 14], [0, 14]]),
    'C': Polygon([[0, 2], [2, 2], [2, 7], [0, 7]]),
}

obstacle = shapely.union_all(obstacles)  # combines obstacle polygons into only one polygon
walkable_area = pedpy.WalkableArea(
    shapely.difference(complete_area, obstacle))  # difference subtracts obstacle form complete_area

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.set_aspect("equal")
pedpy.plot_walkable_area(walkable_area=walkable_area, axes=ax)

for idx, (waypoint, distance) in waypoints.items():
    ax.plot(waypoint[0], waypoint[1], "ro")
    ax.annotate(
        f"{idx}",
        (waypoint[0], waypoint[1]),
        textcoords="offset points",
        xytext=(5, -5),
        ha="center",
    )
    circle = Circle(
        (waypoint[0], waypoint[1]), distance, fc="red", ec="red", alpha=0.1
    )
    ax.add_patch(circle)
for name, exit_polygon in exit_polygons.items():
    x, y = Polygon(exit_polygon).exterior.xy
    plt.fill(x, y, alpha=0.1, color="orange")
    centroid = Polygon(exit_polygon).centroid
    plt.text(centroid.x, centroid.y, f"{name}", ha="center", va="center", fontsize=8)

for name, pol in distribution_polygons.items():
    x, y = pol.exterior.xy
    plt.fill(x, y, alpha=0.1, color="blue")
#%%
G = nx.DiGraph()

# Define nodes with their initial risk levels (0 to 1) and associated costs
# Format: "Node": (risk_level, cost)
nodes = {
    "A": (0.0, 5), "B": (0.0, 2), "C": (0.0, 5),
    "D": (0.6, 2), "E": (0.6, 5), "F": (0.1, 2),
    "G": (0.0, 5), "H": (0.0, 2), "I": (0.0, 5),
    "J": (0.0, 2), "K": (0.0, 5), "L": (0.0, 2),
    "M": (0.0, 5), "N": (0.0, 2), "O": (0.0, 5),
    "P": (0.0, 2), "Q": (0.0, 2), "R": (0.0, 2),
    "S": (0.0, 5), "T": (0.0, 5), "U": (0.0, 5),
    "EA": (0.0, 0), "EB": (0.0, 0), "EC": (0.0, 0),
    "ED": (0.0, 0),
}

# Add nodes to the graph with their attributes
for node, (risk, cost) in nodes.items():
    G.add_node(node, risk=risk)

# Define edges between nodes (directed connections)
# Each tuple represents an edge: (from_node, to_node)
edges = [
    ("P", "A"), ("P", "O"),
    ("A", "P"), ("A", "B"),
    ("B", "A"), ("B", "C"), ("B", "Q"),
    ("C", "B"), ("C", "D"),
    ("D", "C"), ("D", "E"),
    ("E", "D"), ("E", "F"),
    ("F", "E"), ("F", "G"), ("F", "U"), ("F", "EA"),
    ("G", "F"), ("G", "H"),
    ("H", "G"), ("H", "I"),
    ("I", "H"), ("I", "J"), ("I", "EC"),
    ("J", "I"), ("J", "K"), ("J", "S"),
    ("K", "J"), ("K", "L"), ("K", "ED"),
    ("L", "K"), ("L", "M"),
    ("M", "L"), ("M", "N"),
    ("N", "M"), ("N", "T"), ("N", "O"), ("N", "EB"),
    ("T", "N"), ("T", "R"),
    ("R", "T"), ("R", "Q"), ("R", "S"), ("R", "U"),
    ("Q", "B"), ("Q", "R"),
    ("S", "R"), ("S", "J"),
    ("O", "P"), ("O", "N"),
    ("U", "F"), ("U", "R"),
]

# Add edges to the graph with a weight equal to the sum of the costs from both connected nodes.
# For example, for the edge ("P", "A"):
#   - The cost of "P" is 2
#   - The cost of "A" is 5
#   - Weight = 2 + 5 = 7
for u, v in edges:
    # Retrieve the cost of each node from the original dictionary
    cost_u = nodes[u][1]
    cost_v = nodes[v][1]
    weight = cost_u + cost_v
    G.add_edge(u, v, cost=weight)

# Parameters for path calculation
sources = ["A", "C"]  # Starting node for pathfinding
targets = ["EA", "EB", "EC", "ED"]  # Target nodes for pathfinding
#%%
specific_areas = dict()
specific_areas.update(distribution_polygons)
specific_areas['B'] = Polygon([(0,7), (2,7), (2,9), (0,9)])
specific_areas['D'] = Polygon([(0,0), (2,0), (2,2), (0,2)])
specific_areas['E'] = Polygon([(2,0), (14,0), (14,2), (2,2)])
specific_areas['F'] = Polygon([(14,0), (16,0), (16,2), (14,2)])
specific_areas['G'] = Polygon([(16,0), (28,0), (28,2), (16,2)])
specific_areas['H'] = Polygon([(28,0), (30,0), (30,2), (28,2)])
specific_areas['I'] = Polygon([(28,2), (30,2), (30,7), (28,7)])
specific_areas['J'] = Polygon([(28,7), (30,7), (30,9), (28,9)])
specific_areas['K'] = Polygon([(28,9), (30,9), (30,14), (28,14)])
specific_areas['L'] = Polygon([(28,14), (30,14), (30,16), (28,16)])
specific_areas['M'] = Polygon([(16,14), (28,14), (28,16), (16,16)])
specific_areas['N'] = Polygon([(14,14), (16,14), (16,16), (14,16)])
specific_areas['O'] = Polygon([(2,14), (14,14), (14,16), (2,16)])
specific_areas['P'] = Polygon([(0,14), (2,14), (2,16), (0,16)])
specific_areas['Q'] = Polygon([(2,7), (14,7), (14,9), (2,9)])
specific_areas['R'] = Polygon([(14,7), (16,7), (16,9), (14,9)])
specific_areas['S'] = Polygon([(16,7), (28,7), (28,9), (16,9)])
specific_areas['T'] = Polygon([(14,9), (16,9), (16,14), (14,14)])
specific_areas['U'] = Polygon([(14,2), (16,2), (16,7), (14,7)])
specific_areas['EA'] = Polygon([(14, 0), (14, -2), (16, -2), (16, 0)])
specific_areas['EB'] = Polygon([(14, 16), (14, 18), (16, 18), (16, 16)])
specific_areas['EC'] = Polygon([(30, 3.5), (32, 3.5), (32, 5.5), (30, 5.5)])
specific_areas['ED'] = Polygon([(30, 10.5), (32, 10.5), (32, 12.5), (30, 12.5)])
#%%
def remove_obstacles_from_areas(specific_areas, obstacles):
    """
    Removes obstacles from specific areas by subtracting overlapping polygons.

    Args:
        specific_areas (dict): Dictionary of named areas {name: Polygon}.
        obstacles (list): List of Polygon objects representing obstacles.

    Returns:
        dict: Dictionary of cleaned areas {name: Polygon without obstacles}.
    """
    cleaned_areas = {}

    for name, area in specific_areas.items():
        # Subtract all obstacles from the current area
        cleaned_area = area
        for obstacle in obstacles:
            if cleaned_area.intersects(obstacle):  # Only process if they overlap
                cleaned_area = cleaned_area.difference(obstacle)

        # Store the cleaned area in the dictionary
        cleaned_areas[name] = cleaned_area

    return cleaned_areas
#%% md
## Configuration of Simulation Scenarios
#%%
# Dictionary to store simulations for different percentages of agents
simulations = {}

# List of modes of algorithms and Knowledge used for the simulation
modes = [0]

# Total number of agents in the simulation (not currently used in this snippet)
total_agents = 10

# Loop over each percentage value to create a corresponding simulation
for mode in modes:
    # Define the output file path for storing the simulation trajectories
    trajectory_file = f"../sqlite_data/comparing_algorithms_modes_{mode}.sqlite"

    # Create a new simulation instance using JPS (JuPedSim)
    simulation = jps.Simulation(
        model=jps.CollisionFreeSpeedModel(  # Define the agent movement model
            strength_neighbor_repulsion=2.6,  # Strength of repulsion between neighboring agents
            range_neighbor_repulsion=0.1,  # Distance at which agents start repelling each other
            range_geometry_repulsion=0.05,  # Distance at which agents start avoiding obstacles
        ),
        geometry=walkable_area.polygon,  # Define the walkable area for the simulation
        trajectory_writer=jps.SqliteTrajectoryWriter(  # Specify where to store simulation results
            output_file=pathlib.Path(trajectory_file),  # Save output to the specified SQLite file
        ),
    )

    # Store the simulation object in the dictionary using the percentage as a key
    simulations[mode] = simulation
#%% md
## Journey configuration
#%%
def create_journeys_for_simulation(start, paths, waypoint_ids, exit_ids):
    """
    Generates journey descriptions for simulation agents using the best paths obtained previously.

    Args:
        start (str): The starting node in the graph.
        paths (list): A list of paths (each path is a list of nodes).
        waypoint_ids (dict): A dictionary mapping graph node IDs to simulation waypoint IDs.
        exit_ids (dict): A dictionary mapping exit nodes to simulation exit IDs.

    Returns:
        list: A list of tuples, where each tuple contains:
              - A jps.JourneyDescription object describing the agent's journey.
              - The original path (a list of nodes) used to generate the journey.
    """
    if not paths:
        raise ValueError(f"No valid paths found from {start}.")

    journeys = []
    # Iterate over each path from the best_paths list.
    for path in paths:
        # Skip paths that do not have at least two nodes (start and end are required).
        if len(path) < 2:
            continue

        # Map the intermediate graph nodes to simulation waypoint IDs,
        # excluding the start and end nodes.
        needed_waypoints = [waypoint_ids[node] for node in path[1:-1]]
        if not needed_waypoints:
            continue

        # Ensure that the exit node (last node in the path) exists in the exit_ids dictionary.
        if path[-1] not in exit_ids:
            continue

        # Create a JourneyDescription using the intermediate waypoints and append the exit stage.
        journey = jps.JourneyDescription([*needed_waypoints, exit_ids[path[-1]]])

        # Configure transitions between waypoints.
        for idx, waypoint in enumerate(needed_waypoints):
            # If it's the last waypoint, the next stage is the exit (mapped from exit_ids);
            # otherwise, the next stage is the following waypoint.
            next_waypoint = exit_ids[path[-1]] if idx == len(needed_waypoints) - 1 else needed_waypoints[idx + 1]
            journey.set_transition_for_stage(
                waypoint, jps.Transition.create_fixed_transition(next_waypoint)
            )

        # Append the journey description along with its corresponding path.
        journeys.append((journey, path))

    return journeys
#%%
def set_journeys(simulation, start, paths, waypoint_ids, exit_ids):
    """
    Configures agent journeys in the simulation by setting up waypoints, exit stages,
    and journey paths between a start and end point.

    Args:
        simulation (jps.Simulation): The simulation instance where journeys are added.
        start (str): The starting node in the graph.
        end (str): The destination node in the graph.
        paths (dict): A list of paths (each path is a list of nodes)
        waypoint_ids (dict): A dictionary mapping nodes to waypoint IDs in the simulation.
        exit_ids (dict): A dictionary mapping exit nodes to simulation exit IDs.

    Returns:
        tuple:
            - journeys_id (dict): A dictionary mapping the starting node to a list of tuples (journey ID, path) for each journey.
    """

    # Generate different journey paths using the provided graph information
    journeys = create_journeys_for_simulation(start, paths, waypoint_ids, exit_ids)

    # Initialize a dictionary to store journey IDs and their associated paths
    journeys_id = {}

    # Iterate over the generated journeys and their respective paths
    for journey, path in journeys:
        # Add the journey to the simulation and retrieve its unique ID
        journey_id = simulation.add_journey(journey)

        # Ensure the starting node is initialized in the dictionary
        if start not in journeys_id:
            journeys_id[start] = []

        # Store the journey ID and its corresponding path in the dictionary
        journeys_id[start].append((journey_id, path))

    # Return the journey mapping IDs
    return journeys_id
#%% md
## Allocate Agents
#%%
positions = dict()
for source in sources:
    positions[source] = jps.distribute_by_number(
        polygon=distribution_polygons[source],
        number_of_agents=total_agents,
        distance_to_agents=0.4,
        distance_to_polygon=0.7,
        seed=45131502,
    )
#%% md
## Launching the Simulation
#%%
def update_group_paths(simulation_config, risk_per_node, agent_group, G, risk_threshold=0.5):
    """
    Updates the path of a group of agents based on the current node of the first agent in the group.
    If the path is considered unsafe, the path for all agents in the group is updated.

    Args:
        simulation_config (SimulationConfig): Instance containing:
            - simulation: Object managing the simulation (agents and environment).
            - every_nth_frame (int): Interval at which agent paths are updated.
            - waypoints_ids (dict): Mapping from graph nodes to simulation waypoint IDs.
            - journeys_ids (dict): Mapping of journey identifiers to tuples (journey_id, path).
        risk_per_node (dict): Mapping of each node to its risk value.
        agent_group (AgentGroup): An AgentGroup instance containing:
            - agents (list): List of agent IDs.
            - path (list): List representing the group's current path.
            - algorithm (int): Identifier for the algorithm used.
            - knowledge_level (int): The knowledge level of the agents.
        risk_threshold (float): Threshold above which a path segment is considered unsafe.

    Returns:
        AgentGroup: The updated AgentGroup with the new path if a change was made,
                or the original AgentGroup if no update occurred.
    """
    agents_ids = agent_group.agents
    current_path = agent_group.path

    if not agents_ids:
        # No agents in the group; return the original group.
        return agent_group

    simulation = simulation_config.simulation
    waypoints_ids = simulation_config.waypoints_ids

    # Use the first agent in the list to evaluate the path.
    first_agent_id = agents_ids[0]
    # Check if the first agent still exists in the simulation.
    agent_exists = any(agent.id == first_agent_id for agent in simulation.agents())
    if not agent_exists:
        return agent_group

    # Retrieve the agent for path evaluation.
    agent = simulation.agent(first_agent_id)
    current_stage = agent.stage_id  # Current stage ID of the agent.
    next_node = None

    # Find the node corresponding to the agent's current stage.
    for node, waypoint in waypoints_ids.items():
        if waypoint == current_stage:
            next_node = node
            break

    # If no corresponding node is found, return the original group.
    if not next_node:
        return agent_group

    # Attempt to obtain the index of next_node in current_path.
    try:
        node_index = current_path.index(next_node)
    except ValueError:
        # next_node is not in the current_path.
        return agent_group

    # Avoid using a negative index if next_node is the first element in current_path.
    if node_index == 0:
        return agent_group

    # The current node is defined as the node immediately before next_node in the path.
    current_node = current_path[node_index - 1]

    best_path = compute_alternative_path(simulation_config.get_exit_ids_keys(), agent_group, G, current_node, next_node, risk_per_node, risk_threshold)

    # Ensure a valid alternative path was found and that it is different from the current path.
    if best_path is not None and not is_sublist(best_path, current_path):
        journeys_ids = set_journeys(
            simulation, current_node, [best_path], waypoints_ids, simulation_config.exit_ids
        )

        # Assume best_path has at least two nodes.
        next_node = best_path[1]
        next_stage_id = waypoints_ids[next_node]

        new_journey_id, _ = journeys_ids[current_node][0]
        # Update all agents in the group with the new journey and stage.
        for agent_id in agents_ids:
            simulation.switch_agent_journey(agent_id, new_journey_id, next_stage_id)

        agent_group.path = best_path

        # Return the updated agent group with the new path.
        return agent_group

    # If no update is made, return the original agent_group.
    return agent_group
#%%
def simulate_risk(riskSimulationValues, every_nth_frame, G, connection):
    """
    Simulates risk propagation in a graph over multiple frames and stores the results in a database.

    Args:
        iterations (int): Total number of frames to simulate.
        every_nth_frame (int): Interval of frames at which risk updates are performed.
        G (networkx.Graph): Graph where each node has a "risk" attribute.
        propagation_chance (float): Probability of risk spreading between connected nodes.
        increase_chance (float): Probability of individual nodes increasing their risk.
        connection (sqlite3.Connection): Open SQLite database connection to store risk data.
    """
    # Validate the input arguments
    if riskSimulationValues.iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if every_nth_frame <= 0:
        raise ValueError("every_nth_frame must be a positive integer.")

    for frame in range(riskSimulationValues.iterations + 1):
        if frame == 0:
            # Save the initial risk levels of all nodes before any updates
            try:
                write_risk_levels(connection, 0, {node: G.nodes[node]["risk"] for node in G.nodes})
            except Exception as e:
                print(f"Error writing initial risks: {e}")
            continue

        if frame % every_nth_frame == 0:
            try:
                # Update risks in the graph based on propagation and increase chances
                update_risk(G, riskSimulationValues.propagation_chance, riskSimulationValues.increase_chance)
                # Save the updated risk levels for the current frame
                write_risk_levels(connection, frame, {node: G.nodes[node]["risk"] for node in G.nodes})
            except Exception as e:
                print(f"Error updating risks at frame {frame}: {e}")
#%%
def run_agent_simulation(simulation_config, agent_groups, G, risk_threshold):
    """
    Runs the agent simulation, updating agent paths based on current risk levels retrieved from the database.

    Args:
        simulation_config (SimulationConfig): An instance of SimulationConfig containing:
            - simulation: The simulation object managing agents and the environment.
            - every_nth_frame (int): The interval at which agent paths are updated.
            - waypoints_ids (dict): Mapping of graph node IDs to simulation waypoint IDs.
        agent_group (dict): Mapping of starting nodes to AgentGroups.
        risk_threshold (float): The risk level threshold above which agents will attempt to avoid high-risk areas.
    """
    while simulation_config.simulation.agent_count() > 0:
        # Advance the simulation by one frame
        simulation_config.simulation.iterate()
        frame = simulation_config.simulation.iteration_count()

        # Update agent paths only at specified intervals
        if frame % every_nth_frame == 0:
            try:
                # Fetch risk levels for the current frame from the database
                risk_this_frame = get_risk_levels_by_frame(connection, frame)

                # Update paths for the agents based on current risks and threshold
                for key, agent_group in agent_groups.items():
                    agent_groups[key] = update_group_paths(
                        simulation_config, risk_this_frame, agent_group, G, risk_threshold=risk_threshold
                    )
            except Exception as e:
                print(f"Error updating paths at frame {frame}: {e}")
#%%
def set_agents_in_simulation(simulation, positions, journey_id, firt_waypoint_id):
    agents = []
    for position in positions:  # Use the second half of the positions
        # Add agents with specified parameters (e.g., position, journey, velocity)
        agents.append(
            simulation.add_agent(
                jps.CollisionFreeSpeedModelAgentParameters(
                    position=position,       # Initial position of the agent
                    journey_id=journey_id,   # Journey ID for the agent
                    stage_id=first_waypoint_id,  # Starting waypoint for the agent
                    v0=0.8                   # Desired maximum speed of the agent
                )
            )
        )
    return agents
#%%
# False -> to use the default risk evolution, True -> random risk evolution
use_random_risk_layout = True

# set agent groups
knowledge_levels_per_group = [0, 1, 0, 1]
algorithm_per_group = [0, 1, 1, 0]
#%%
# Simulation parameters
riskSimulationValues = RiskSimulationValues(6000, 0.001, 0.01)

every_nth_frame = 50  # Interval of frames for risk updates

# Establish a connection to the appropriate SQLite database
default_connection_file = "../sqlite_data/default_comparing_algorithms_risks.db"  # default risk evolution file
new_connection_file = "../sqlite_data/comparing_algorithms_risks.db"  # random risk evolution file
if use_random_risk_layout:
    connection_file = new_connection_file  # Use new database if random risk layout is enabled
else:
    connection_file = default_connection_file  # Use default database otherwise

connection = sqlite3.connect(connection_file)
try:
    if use_random_risk_layout:
        # Create or reset the risk table if random risk layout is enabled
        create_risk_table(connection)

        # Simulate risk propagation and store results in the database
        simulate_risk(riskSimulationValues, every_nth_frame, G, connection)
finally:
    # Ensure the database connection is closed after operations
    connection.close()

trajectory_files = {}
for mode, simulation in simulations.items():

    exit_ids = {}
    for node, exit_polygon in exit_polygons.items():
        exit_ids[node] = simulation.add_exit_stage(exit_polygon)

    # Initialize a dictionary to store waypoint IDs
    waypoints_ids = {}
    # Convert waypoints into simulation waypoints with associated distances
    for node, (waypoint, distance) in waypoints.items():
        waypoints_ids[node] = simulation.add_waypoint_stage(waypoint, distance)

    agent_groups = dict()
    for source in sources:
        agent_group_aux = AgentGroup(None, None, algorithm_per_group[mode], knowledge_levels_per_group[mode])
        path = compute_alternative_path(exit_polygons.keys(), agent_group_aux, G, source)

        # Set up a journey for the simulation
        journeys_ids = set_journeys(
            simulation, source, [path], waypoints_ids, exit_ids
        )

        # Retrieve the best path for the first source and its associated journey ID
        journey_id, best_path_source = journeys_ids[source][0]
        next_node = best_path_source[1]  # Get the next node on the best path
        first_waypoint_id = waypoints_ids[next_node]  # Determine the waypoint ID for the next node

        agents = set_agents_in_simulation(simulation, positions[source], journey_id, first_waypoint_id)

        agent_group_aux.path = path
        agent_group_aux.agents = agents

        agent_groups[source] = agent_group_aux

    simulation_config = SimulationConfig(simulation, every_nth_frame, waypoints_ids, exit_ids)

    ## Calculate the number of items based on the percentage of positions
    # num_items = int(len(positions) * (percentage / 100.0))

    connection = sqlite3.connect(connection_file)
    # Run the agent simulation, updating paths based on the risk levels
    run_agent_simulation(
        simulation_config,
        agent_groups,
        G,
        risk_threshold=0.5,  # Threshold for avoiding high-risk areas
    )

    connection.close()

    # Generate the trajectory file for the current percentage and store its path
    trajectory_file = f"../sqlite_data/comparing_algorithms_modes_{mode}.sqlite"
    trajectory_files[mode] = trajectory_file
#%%
# Open the database connection safely
with sqlite3.connect(connection_file) as connection:
    # Fetch all risk data grouped by frame
    all_risks = get_risks_grouped_by_frame(connection)

    # Iterate over the nested dictionary
    for frame, areas in all_risks.items():  # 'areas' is a dictionary {area: risk_level}
        for area, risk in areas.items():
            print(f"Frame {frame}, Area {area}: Risk Level {risk}")

# Connection automatically closes when 'with' block ends
#%% md
## Visualizing Agent Pathways
#%%
agent_trajectories = {}
for mode in modes:
    trajectory_file = trajectory_files[mode]
    agent_trajectories[mode], walkable_area = read_sqlite_file(
        trajectory_file
    )
    animate(
        agent_trajectories[mode],
        walkable_area,
        title_note=f"Mode: {mode}",
        risk_per_frame=all_risks,
        specific_areas=specific_areas
    ).show()