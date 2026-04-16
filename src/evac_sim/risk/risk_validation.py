def validate_risk_inputs(
    *,
    graph,
    exits,
    risk_iterations,
    every_nth_frame,
    increase_chance,
    propagation_threshold,
    risk_threshold,
    starting_risks,
    risk_overrides,
):
    if risk_iterations <= 0:
        raise ValueError("risk_iterations must be > 0")

    if every_nth_frame <= 0:
        raise ValueError("every_nth_frame must be > 0")

    if not 0.0 <= increase_chance <= 1.0:
        raise ValueError("increase_chance must be in [0, 1]")

    if not 0.0 <= propagation_threshold <= 1.0:
        raise ValueError("propagation_threshold must be in [0, 1]")

    if not 0.0 <= risk_threshold <= 1.0:
        raise ValueError("risk_threshold must be in [0, 1]")

    graph_nodes = set(graph.nodes)

    for exit_node in exits:
        if exit_node not in graph_nodes:
            raise ValueError(f"Exit node '{exit_node}' is not present in graph")

    for node_id, risk_val in starting_risks:
        if node_id not in graph_nodes:
            raise ValueError(f"starting_risks contains unknown node '{node_id}'")
        if not 0.0 <= float(risk_val) <= 1.0:
            raise ValueError(f"starting risk for node '{node_id}' must be in [0, 1]")

    for frame, node_id, risk_val in risk_overrides:
        if int(frame) < 0:
            raise ValueError(f"risk override frame must be >= 0, got {frame}")
        if node_id not in graph_nodes:
            raise ValueError(f"risk_overrides contains unknown node '{node_id}'")
        if not 0.0 <= float(risk_val) <= 1.0:
            raise ValueError(f"risk override for node '{node_id}' must be in [0, 1]")

    seen = set()
    for node_id, _ in starting_risks:
        if node_id in seen:
            raise ValueError(f"Duplicate starting risk for node '{node_id}'")
        seen.add(node_id)

    seen = set()
    for frame, node_id, _ in risk_overrides:
        key = (int(frame), node_id)
        if key in seen:
            raise ValueError(f"Duplicate risk override for frame={frame}, node='{node_id}'")
        seen.add(key)