def compute_current_nodes(simulation_config, agent_group, frame) -> None:
    """
    Computes the current node for each agent in the agent_group based on its stage_id.
    The function avoids returning None by applying a consistent fallback policy.
    """
    simulation = simulation_config.simulation
    current_path = agent_group.path or []

    # Fallback node when the current node cannot be determined
    fallback_node = current_path[-1] if current_path else None

    if not current_path:
        agent_group.current_nodes = {
            agent_id: None for agent_id in agent_group.agents
        }
        return

    # Precompute existing agents
    existing_ids = {agent.id for agent in simulation.agents()}

    # Build reverse mapping: stage_id -> node
    stage_to_node = {}
    for node, stage_id in simulation_config.waypoints_ids.items():
        stage_to_node[stage_id] = node
    for node, stage_id in simulation_config.exit_ids.items():
        stage_to_node[stage_id] = node

    # Map nodes to their index in the current path
    node_to_index = {node: idx for idx, node in enumerate(current_path)}

    computed_current_nodes = {}

    for agent_id in agent_group.agents:
        if agent_id not in existing_ids:
            computed_current_nodes[agent_id] = fallback_node
            continue

        agent = simulation.agent(agent_id)
        next_node = stage_to_node.get(agent.stage_id)

        if next_node is None:
            computed_current_nodes[agent_id] = fallback_node
            continue

        node_index = node_to_index.get(next_node)
        if node_index is None:
            computed_current_nodes[agent_id] = fallback_node
        elif node_index == 0:
            computed_current_nodes[agent_id] = current_path[0]
        else:
            computed_current_nodes[agent_id] = current_path[node_index - 1]

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
