import random

import networkx as nx

from evac_sim.db.danger_sim_db_manager import *


def update_risk(G: nx.DiGraph, increase_chance=0.2, propagation_threshold=0.5):
    """
    Updates the risk levels of nodes in the graph.

    The update combines (i) random local increases and (ii) deterministic, symmetric propagation:
      - If a node has risk >= propagation_threshold, it becomes an active emitter.
      - Its direct neighbors (in an undirected sense) receive a propagated risk level equal to one-third of its risk.
      - Second-order neighbors (excluding the original node and its direct neighbors) receive one-ninth of its risk.
      - Nodes with risk 0 do not increase randomly unless they are affected by propagation from an active emitter.

    Args:
        G (nx.DiGraph): Graph with nodes and edges. Each node must have a "risk" attribute in [0, 1].
        increase_chance (float): Probability of randomly increasing the risk of a node (only if its current risk > 0).
        propagation_threshold (float): Risk level above which a node becomes an active emitter and propagates risk.
    """
    new_risks = {}

    # Randomly update the risk for each node,
    # except for nodes with risk 0 (unless they are affected by active-emitter propagation).
    for node in G.nodes:
        current_risk = G.nodes[node]["risk"]
        if current_risk > 0 and random.random() < increase_chance:
            current_risk = min(1.0, current_risk + random.uniform(0.05, 0.2))
        new_risks[node] = round(current_risk, 1)

    # Convert the graph to an undirected version for symmetric propagation.
    UG = G.to_undirected()

    # Deterministic propagation from active emitters (risk >= propagation_threshold).
    for node in G.nodes:
        node_risk = G.nodes[node]["risk"]
        if node_risk >= propagation_threshold:
            # First level: direct neighbors receive one-third of the emitter's risk.
            risk_direct = round(node_risk / 3, 1)
            for neighbor in UG.neighbors(node):
                new_risks[neighbor] = max(
                    new_risks.get(neighbor, G.nodes[neighbor]["risk"]), risk_direct
                )

            # Second level: neighbors of direct neighbors (excluding the original node and its direct neighbors).
            first_level = set(UG.neighbors(node))
            risk_second = round(node_risk / 9, 1)
            for neighbor in first_level:
                for second_neighbor in UG.neighbors(neighbor):
                    if second_neighbor == node or second_neighbor in first_level:
                        continue
                    new_risks[second_neighbor] = max(
                        new_risks.get(second_neighbor, G.nodes[second_neighbor]["risk"]),
                        risk_second,
                    )

    # Apply the new risk values to the graph.
    for node, risk in new_risks.items():
        G.nodes[node]["risk"] = risk


def simulate_risk(risk_sim_values, every_nth_frame, G, exits, connection, seed=None):
    """
    Simulates risk evolution in a graph over multiple frames and stores the results in a database.

    Args:
        risk_sim_values: An object with attributes:
            - iterations (int): Total number of frames to simulate.
            - start_frame (int): Initial frame (if used).
            - max_risk_increment (float): Maximum risk increment per step (if used).
            - increase_chance (float): Probability of random risk increase per update.
            - propagation_threshold (float): Risk level above which a node becomes an active emitter.
            - risk_overrides (list of (int, str, float) tuples, optional):
                Overrides to forcibly set node risk at specific frames.
            - starting_risks (list of (str, float) tuples, optional):
                Defines initial risk values for specific nodes.
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
            # Apply starting risks
            for node_id, risk_val in risk_sim_values.starting_risks:
                if node_id in G.nodes:
                    G.nodes[node_id]["risk"] = risk_val

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

        # Directly use the iteration as frames
        if frame % every_nth_frame == 0:
            try:
                # Update risks in the graph based on propagation and random increase chance
                update_risk(
                    G, risk_sim_values.increase_chance, risk_sim_values.propagation_threshold
                )

                # Ensure that exit nodes retain a risk of 0 after the update
                for exit_node in exits:
                    if exit_node in G.nodes:
                        G.nodes[exit_node]["risk"] = 0

                # Save the updated risk levels for the current frame
                write_risk_levels(
                    connection, frame, {node: G.nodes[node]["risk"] for node in G.nodes}
                )
            except Exception as e:
                print(f"Error updating risks at frame {frame}: {e}")
