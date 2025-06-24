import networkx as nx
import random

from Py.database.danger_sim_db_manager import *

def update_risk(G: nx.DiGraph, increase_chance=0.2, danger_threshold=0.5):
    """
    Updates the risk levels of nodes in the graph.
    This function eliminates probabilistic risk propagation and instead propagates risk symmetrically:
      - If a node has a risk >= danger_threshold, it is considered dangerous.
      - Its direct neighbors (in an undirected sense) receive a risk increase equal to one-third of its risk.
      - The neighbors of these (excluding the original node and its direct neighbors) receive a risk increase of one-ninth of its risk.
      - Nodes with a risk of 0 will not have their risk increased randomly unless affected by propagation from dangerous nodes.

    Args:
        G (nx.DiGraph): Graph with nodes and edges.
        increase_chance (float): Chance to increase the base risk of each node.
        danger_threshold (float): Threshold above which a node is considered dangerous.
    """
    new_risks = {}

    # Randomly update the risk for each node,
    # except for nodes with risk 0 (unless they are affected by dangerous node propagation)
    for node in G.nodes:
        current_risk = G.nodes[node]["risk"]
        if current_risk > 0 and random.random() < increase_chance:
            current_risk = min(1.0, current_risk + random.uniform(0.05, 0.2))
        new_risks[node] = round(current_risk, 1)

    # Convert the graph to an undirected version for symmetric propagation.
    UG = G.to_undirected()

    # Deterministic propagation from dangerous nodes symmetrically.
    for node in G.nodes:
        node_risk = G.nodes[node]["risk"]
        if node_risk >= danger_threshold:
            # First level: direct neighbors (in undirected sense) receive one-third of the node's risk.
            risk_direct = round(node_risk / 3, 1)
            for neighbor in UG.neighbors(node):
                new_risks[neighbor] = max(new_risks.get(neighbor, G.nodes[neighbor]["risk"]), risk_direct)
            # Second level: neighbors of direct neighbors
            # Exclude the original node and its direct neighbors to avoid overlaps.
            first_level = set(UG.neighbors(node))
            for neighbor in first_level:
                for second_neighbor in UG.neighbors(neighbor):
                    if second_neighbor == node or second_neighbor in first_level:
                        continue
                    risk_second = round(node_risk / 9, 1)
                    new_risks[second_neighbor] = max(
                        new_risks.get(second_neighbor, G.nodes[second_neighbor]["risk"]), risk_second
                    )

    # Apply the new risk values to the graph.
    for node, risk in new_risks.items():
        G.nodes[node]["risk"] = risk

def simulate_risk(risk_sim_values, every_nth_frame, G, exits, connection, seed=None):
    """
        Simulates risk propagation in a graph over multiple frames and stores the results in a database.

        Args:
            risk_sim_values: An object with attributes:
                - iterations (int): Total number of frames to simulate.
                - start_frame (int): Initial frame (if used).
                - max_risk_increment (float): Maximum risk increment per step (if used).
                - increase_chance (float): Probability of risk increase per propagation.
                - danger_threshold (float): Risk level considered dangerous.
                - risk_overrides (list of (int, str, float) tuples, optional):
                    Overrides to forcibly set node risk at specific frames.
            every_nth_frame (int): How often (in frames) to save results.
            G: NetworkX graph on which the simulation runs.
            exits (list of str): List of exit-node identifiers.
            connection: Database connection for writing results.
            seed (int, optional): Seed for random number generator for reproducibility.
    """
    # Validate the input arguments
    if risk_sim_values.iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if every_nth_frame <= 0:
        raise ValueError("every_nth_frame must be a positive integer.")

    if seed is not None:
        random.seed(seed)

    for frame in range(risk_sim_values.iterations + 1):

        for f, node_id, risk_val in risk_sim_values.risk_overrides:
            if frame == f and node_id in G.nodes:
                G.nodes[node_id]["risk"] = risk_val

        if frame == 0:
            # Ensure that exit nodes have risk 0
            for exit_node in exits:
                if exit_node in G.nodes:
                    G.nodes[exit_node]["risk"] = 0
            # Save the initial risk levels of all nodes before any updates
            try:
                write_risk_levels(connection, 0, {node: G.nodes[node]["risk"] for node in G.nodes})
            except Exception as e:
                print(f"Error writing initial risks: {e}")
            continue

        # directly use the iteration as frames
        if frame % every_nth_frame == 0:
            try:
                # Update risks in the graph based on propagation and increase chances
                update_risk(G,risk_sim_values.increase_chance, risk_sim_values.danger_threshold)

                # Ensure that exit nodes retain a risk of 0 after the update
                for exit_node in exits:
                    if exit_node in G.nodes:
                        G.nodes[exit_node]["risk"] = 0

                # Save the updated risk levels for the current frame
                write_risk_levels(connection, frame, {node: G.nodes[node]["risk"] for node in G.nodes})
            except Exception as e:
                print(f"Error updating risks at frame {frame}: {e}")