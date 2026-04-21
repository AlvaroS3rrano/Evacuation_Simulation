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

    # k edges => k+1 nodes
    max_nodes = max(1, horizon_k + 1)
    return remaining_path[:max_nodes]

def update_group_reserved_edges(
    env_info,
    group: AgentGroup,
    *,
    frame: int | None = None,
    group_id: str | int | None = None,
    group_size_override: int | None = None,
    horizon_k: int | None = None,
) -> None:
    current_group_size = (
        group_size_override if group_size_override is not None else len(group.agents)
    )
    old_reserved_edges = getattr(group, "reserved_edges", set())
    old_reserved_group_size = getattr(group, "reserved_group_size", 0)

    reserved_path = get_reserved_path_segment(group, horizon_k=horizon_k)
    new_reserved_edges = {(u, v) for u, v in zip(reserved_path, reserved_path[1:])}

    to_release = old_reserved_edges - new_reserved_edges
    to_add = new_reserved_edges - old_reserved_edges
    kept_edges = old_reserved_edges & new_reserved_edges

    # 1) Release edges no longer reserved using OLD reserved size
    for u, v in to_release:
        if env_info.graph.has_edge(u, v):
            env_info.graph[u][v]["occupancy"] = max(
                0,
                env_info.graph[u][v].get("occupancy", 0) - old_reserved_group_size
            )

    # 2) If group size changed, adjust kept edges by delta
    size_delta = current_group_size - old_reserved_group_size
    if size_delta != 0:
        for u, v in kept_edges:
            if env_info.graph.has_edge(u, v):
                env_info.graph[u][v]["occupancy"] = max(
                    0,
                    env_info.graph[u][v].get("occupancy", 0) + size_delta
                )

    # 3) Add newly reserved edges using CURRENT size
    for u, v in to_add:
        if env_info.graph.has_edge(u, v):
            env_info.graph[u][v]["occupancy"] = env_info.graph[u][v].get("occupancy", 0) + current_group_size

    logger.info(
        "Reservation update | frame=%s group=%s agents=%d old_edges=%d new_edges=%d add=%d release=%d delta=%d",
        frame,
        group_id,
        current_group_size,
        len(old_reserved_edges),
        len(new_reserved_edges),
        len(to_add),
        len(to_release),
        size_delta,
    )

    for u, v in sorted(to_add):
        if env_info.graph.has_edge(u, v):
            logger.debug(
                "Reserve edge | frame=%s group=%s edge=(%s,%s) occupancy=%s",
                frame,
                group_id,
                u,
                v,
                env_info.graph[u][v]["occupancy"],
            )

    for u, v in sorted(to_release):
        if env_info.graph.has_edge(u, v):
            logger.debug(
                "Release edge | frame=%s group=%s edge=(%s,%s) occupancy=%s",
                frame,
                group_id,
                u,
                v,
                env_info.graph[u][v]["occupancy"],
            )

    group.reserved_edges = new_reserved_edges
    group.reserved_group_size = current_group_size

def release_group_reserved_edges(env_info, group: AgentGroup) -> None:
    reserved_edges = getattr(group, "reserved_edges", set())
    reserved_group_size = getattr(group, "reserved_group_size", 0)

    for u, v in reserved_edges:
        if env_info.graph.has_edge(u, v):
            env_info.graph[u][v]["occupancy"] = max(
                0,
                env_info.graph[u][v].get("occupancy", 0) - reserved_group_size
            )


def restore_group_reserved_edges(env_info, group: AgentGroup) -> None:
    reserved_edges = getattr(group, "reserved_edges", set())
    reserved_group_size = getattr(group, "reserved_group_size", 0)

    for u, v in reserved_edges:
        if env_info.graph.has_edge(u, v):
            env_info.graph[u][v]["occupancy"] = (
                env_info.graph[u][v].get("occupancy", 0) + reserved_group_size
            )
