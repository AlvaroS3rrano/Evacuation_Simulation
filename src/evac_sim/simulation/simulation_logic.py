from evac_sim.core.agent_group import AgentGroup

import logging

logger = logging.getLogger(__name__)

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
        agent_group.current_nodes = {agent_id: None for agent_id in agent_group.agents}
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
            is_stairs = G.nodes[current_node].get("is_stairs", False)
            if is_stairs:
                # Set the agent's speed to stairs_max_speed when on a staircase
                agent.model.v0 = simulation_config.stairs_max_speed
            else:
                # Otherwise, use the normal maximum speed
                agent.model.v0 = simulation_config.normal_max_speed
        else:
            # If the current node is undefined, default to normal speed
            agent.model.v0 = simulation_config.normal_max_speed

def path_to_edges(path):
    return {(u, v) for u, v in zip(path, path[1:])}

def get_remaining_path_for_group(group: AgentGroup):
    if not group.path or not group.current_nodes:
        return []

    max_idx = -1
    for aid in group.agents:
        area = group.current_nodes.get(aid)
        if area is None:
            continue
        try:
            idx = group.path.index(area)
        except ValueError:
            continue
        if idx > max_idx:
            max_idx = idx

    if max_idx < 0:
        return list(group.path)

    return group.path[max_idx:]


def get_reserved_path_segment(group: AgentGroup, horizon_k: int | None = None):
    remaining_path = get_remaining_path_for_group(group)

    if horizon_k is None:
        return remaining_path

    # k edges => k + 1 nodes
    max_nodes = max(1, horizon_k + 1)
    return remaining_path[:max_nodes]


def _add_edge_flow_occupancy(env_info, edge: tuple, delta: int) -> None:
    u, v = edge

    if not env_info.graph.has_edge(u, v):
        return

    edge_data = env_info.graph[u][v]
    edge_data["flow_occupancy"] = max(
        0,
        int(edge_data.get("flow_occupancy", 0)) + delta,
    )


def _add_node_occupancy(env_info, node, delta: int) -> None:
    if node not in env_info.graph.nodes:
        return

    node_data = env_info.graph.nodes[node]
    node_data["node_occupancy"] = max(
        0,
        int(node_data.get("node_occupancy", 0)) + delta,
    )


def update_group_reserved_edges(
    env_info,
    group: AgentGroup,
    *,
    frame: int | None = None,
    group_id: str | int | None = None,
    group_size_override: int | None = None,
    horizon_k: int | None = None,
) -> None:
    """
    Update static h1/h2 reservations.

    The function name is kept for compatibility, but the reservation model now
    tracks:
      - flow_occupancy on edges
      - node_occupancy on destination nodes

    h1 reserves the whole remaining path.
    h2 reserves only the first horizon_k edges and their destination nodes.
    """
    current_group_size = (
        group_size_override if group_size_override is not None else len(group.agents)
    )

    current_group_size = max(0, int(current_group_size))

    old_reserved_edges = getattr(group, "reserved_edges", set())
    old_reserved_nodes = getattr(group, "reserved_nodes", set())
    old_reserved_group_size = getattr(group, "reserved_group_size", 0)

    reserved_path = get_reserved_path_segment(
        group,
        horizon_k=horizon_k,
    )

    new_reserved_edges = {
        (u, v)
        for u, v in zip(reserved_path, reserved_path[1:])
    }

    # The cost model evaluates the destination node of each step u -> v.
    # Therefore the static reservation model reserves the same target nodes.
    new_reserved_nodes = set(reserved_path[1:])

    edges_to_release = old_reserved_edges - new_reserved_edges
    edges_to_add = new_reserved_edges - old_reserved_edges
    kept_edges = old_reserved_edges & new_reserved_edges

    nodes_to_release = old_reserved_nodes - new_reserved_nodes
    nodes_to_add = new_reserved_nodes - old_reserved_nodes
    kept_nodes = old_reserved_nodes & new_reserved_nodes

    # 1) Release no longer reserved edges/nodes using old group size
    for edge in edges_to_release:
        _add_edge_flow_occupancy(
            env_info,
            edge,
            -old_reserved_group_size,
        )

    for node in nodes_to_release:
        _add_node_occupancy(
            env_info,
            node,
            -old_reserved_group_size,
        )

    # 2) Adjust kept reservations if group size changed
    size_delta = current_group_size - old_reserved_group_size

    if size_delta != 0:
        for edge in kept_edges:
            _add_edge_flow_occupancy(
                env_info,
                edge,
                size_delta,
            )

        for node in kept_nodes:
            _add_node_occupancy(
                env_info,
                node,
                size_delta,
            )

    # 3) Add newly reserved edges/nodes using current group size
    for edge in edges_to_add:
        _add_edge_flow_occupancy(
            env_info,
            edge,
            current_group_size,
        )

    for node in nodes_to_add:
        _add_node_occupancy(
            env_info,
            node,
            current_group_size,
        )

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Static reservation update | frame=%s group=%s agents=%d "
            "old_edges=%d new_edges=%d old_nodes=%d new_nodes=%d "
            "edge_add=%d edge_release=%d node_add=%d node_release=%d delta=%d",
            frame,
            group_id,
            current_group_size,
            len(old_reserved_edges),
            len(new_reserved_edges),
            len(old_reserved_nodes),
            len(new_reserved_nodes),
            len(edges_to_add),
            len(edges_to_release),
            len(nodes_to_add),
            len(nodes_to_release),
            size_delta,
        )

    group.reserved_edges = new_reserved_edges
    group.reserved_nodes = new_reserved_nodes
    group.reserved_group_size = current_group_size


def release_group_reserved_edges(env_info, group: AgentGroup) -> None:
    """
    Release static h1/h2 reservations.

    The function name is kept for compatibility.
    """
    reserved_edges = getattr(group, "reserved_edges", set())
    reserved_nodes = getattr(group, "reserved_nodes", set())
    reserved_group_size = getattr(group, "reserved_group_size", 0)

    for edge in reserved_edges:
        _add_edge_flow_occupancy(
            env_info,
            edge,
            -reserved_group_size,
        )

    for node in reserved_nodes:
        _add_node_occupancy(
            env_info,
            node,
            -reserved_group_size,
        )


def restore_group_reserved_edges(env_info, group: AgentGroup) -> None:
    """
    Restore static h1/h2 reservations.

    The function name is kept for compatibility.
    """
    reserved_edges = getattr(group, "reserved_edges", set())
    reserved_nodes = getattr(group, "reserved_nodes", set())
    reserved_group_size = getattr(group, "reserved_group_size", 0)

    for edge in reserved_edges:
        _add_edge_flow_occupancy(
            env_info,
            edge,
            reserved_group_size,
        )

    for node in reserved_nodes:
        _add_node_occupancy(
            env_info,
            node,
            reserved_group_size,
        )