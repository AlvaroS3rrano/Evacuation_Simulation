from typing import Any, Dict


def update_all_graph_risks(EnvInf, risk_per_node: Dict[Any, float], default: float = 0.0) -> None:
    """
    Update the 'risk' attribute of all nodes in the environment graphs.

    This function synchronizes the risk values used by routing algorithms with
    the most recent risk estimation results stored in `risk_per_node`.

    The update is applied to:
      - the global routing graph (`EnvInf.graph`)
      - all per-floor routing graphs (`EnvInf.floors`), if present

    Nodes that do not appear in `risk_per_node` are assigned the provided
    default risk value.

    Args:
        EnvInf: Environment information object containing:
            - graph: the global routing graph
            - floors (dict | None): optional mapping {floor_id: floor_graph}
        risk_per_node (dict): Mapping {node_id: risk_value}.
        default (float): Risk value assigned to nodes missing from `risk_per_node`.

    Returns:
        None
    """
    # --- Update global graph ---
    for node in EnvInf.graph.nodes:
        EnvInf.graph.nodes[node]["risk"] = risk_per_node.get(node, default)

    # --- Update per-floor graphs (if available) ---
    if EnvInf.floors is not None:
        for _, floor_graph in EnvInf.floors.items():
            for node in floor_graph.nodes:
                floor_graph.nodes[node]["risk"] = risk_per_node.get(node, default)
