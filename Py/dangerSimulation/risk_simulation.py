import networkx as nx
import random
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