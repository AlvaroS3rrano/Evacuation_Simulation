import jupedsim as jps
import json
from statistics import mean, pvariance

from Py.classes.agentGroup import AgentGroup
from Py.database.danger_sim_db_manager import get_risk_levels_by_frame
from Py.database.agent_area_db_manager import write_agent_area
from Py.pathFinding.settingPaths import compute_alternative_path, is_sublist
from Py.journey_configuration import set_journeys
from Py.simulation_logic import compute_current_nodes, update_agent_speed_on_stairs
from Py.database.group_path_db_manager import write_group_path_data


def validate_agent(agent_id: int, simulation, current_nodes: dict) -> bool:
    """
    Check if an agent exists in the simulation and has a recorded current node.
    Returns True if valid, False otherwise.
    """
    exists = any(agent.id == agent_id for agent in simulation.agents())
    has_node = agent_id in current_nodes
    return exists and has_node


def try_get_node_index(node, path: list) -> int:
    """
    Attempt to find the index of a node in a path list.
    Returns the index or -1 if not found.
    """
    try:
        return path.index(node)
    except ValueError:
        return -1


def update_group_paths(sim_cfg, risk_map: dict, group: AgentGroup,
                       env_info, threshold: float = 0.5) -> AgentGroup:
    """
    Evaluate each agent (or first agent if awareness is low) and reroute the group's path
    if a safer alternative is found.
    """
    agent_ids = group.agents
    if not agent_ids:
        return group

    current_path = group.path
    current_nodes = group.current_nodes
    simulation = sim_cfg.simulation
    waypoints = sim_cfg.waypoints_ids

    # Choose the agent in the front of the group
    to_check = [max(agent_ids, key=lambda aid: current_path.index(current_nodes[aid]))]

    for aid in to_check:
        if not validate_agent(aid, simulation, current_nodes):
            return group

        curr_node = current_nodes[aid]
        idx = try_get_node_index(curr_node, current_path)
        if idx < 0 or idx == len(current_path) - 1:
            continue

        next_node = current_path[idx + 1]
        alt_path = compute_alternative_path(
            sim_cfg.get_exit_ids_keys(), group, env_info,
            curr_node, next_node,
            risk_map, threshold, sim_cfg.gamma
        )

        if alt_path and not is_sublist(alt_path, current_path):
            # Build and assign new journey for all agents
            journeys = set_journeys(
                simulation, curr_node,
                [alt_path], waypoints, sim_cfg.exit_ids
            )
            new_node = alt_path[1]
            stage_id = waypoints[new_node]
            new_jid, _ = journeys[curr_node][0]

            for aid in agent_ids:
                simulation.switch_agent_journey(aid, new_jid, stage_id)

            group.path = alt_path
            return group

    return group


def record_group_path_data(gr_pth_conn, frame: int, group_id: int,
                            group: AgentGroup, risks: dict):
    """
    Compute risk estimates and record dynamic path-choice data for a group at a given frame.
    """
    # Map numeric level to string
    algorithm = 'Centtrality' if group.algorithm == 1 else 'Efficient'
    awareness = 'High' if group.awareness_level == 1 else 'Low'
    # Current area
    max_idx = -1
    current_area = None
    for aid in group.agents:
        area = group.current_nodes.get(aid)
        if area is None:
            continue
        try:
            idx = group.path.index(area)
        except ValueError:
            idx = -1
        if idx > max_idx:
            max_idx = idx
            current_area = area

    if current_area is None and group.agents:
        current_area = group.current_nodes[group.agents[0]]
    # Remaining path
    if max_idx >= 0:
        next_path = group.path[max_idx:]
    else:
        next_path = group.path
    # Compute risk estimates over remaining path
    risk_values = [risks.get(area, 0.0) for area in next_path]
    est_risk_mean = mean(risk_values) if risk_values else 0.0
    est_risk_max = max(risk_values) if risk_values else 0.0
    est_risk_min = min(risk_values) if risk_values else 0.0
    est_risk_var = pvariance(risk_values) if len(risk_values) > 1 else 0.0
    # Instantaneous risk at current area
    risk_now = risks.get(current_area, 0.0)

    # Record to database
    write_group_path_data(
        gr_pth_conn,
        frame,
        group_id,
        algorithm,
        awareness,
        current_area,
        next_path,
        est_risk_mean,
        est_risk_max,
        est_risk_min,
        est_risk_var,
        risk_now
    )


def process_frame(sim_cfg, groups: dict, env_info, conn, area_conn, gr_pth_conn, frame: int, threshold: float):
    """
    Compute current nodes, log agent areas, adjust speeds, update paths for each group, and record path-choice data.
    """
    # Retrieve risk map for this frame (area_id -> risk value)
    risks = get_risk_levels_by_frame(conn, frame)

    for group_id, group in groups.items():
        # Compute each agent's current node
        compute_current_nodes(sim_cfg, group, frame)
        # Log agent areas
        write_agent_area(area_conn, frame, group.agents, group.current_nodes, risks)
        # Update speeds on stairs if needed
        update_agent_speed_on_stairs(env_info.graph, sim_cfg, group)
        # Potentially reroute group
        group = update_group_paths(sim_cfg, risks, group, env_info, threshold)
        # Record path-choice data
        record_group_path_data(gr_pth_conn, frame, group_id, group, risks)

        groups[group_id] = group


def run_agent_simulation(sim_cfg, agent_groups: dict, env_info, conn, area_conn, gr_pth_conn, threshold: float):
    """
    Advance the simulation and periodically process agent movements and path updates.
    """
    sim = sim_cfg.simulation
    # Initial logging at frame zero
    if sim.agent_count() > 0:
        process_frame(sim_cfg, agent_groups, env_info, conn, area_conn, gr_pth_conn, 0, threshold)

    # Main loop: iterate until no agents remain
    while sim.agent_count() > 0:
        sim.iterate()
        iteration = sim.iteration_count()

        # Trigger at configured simulation intervals
        if iteration % sim_cfg.every_nth_frame_simulation == 0:
            frame = iteration // sim_cfg.every_nth_frame_simulation
            if frame % sim_cfg.every_nth_frame_animation == 0:
                try:
                    process_frame(sim_cfg, agent_groups, env_info, conn, area_conn, gr_pth_conn, frame, threshold)
                except Exception as exc:
                    print(f"Error at frame {frame}: {exc}")


def set_agents_in_simulation(simulation, positions: list, journey_id: int,
                             waypoint_id: int, speed: float) -> list:
    """
    Add multiple agents to the simulation with the same journey and speed.

    Returns a list of new agent instances.
    """
    new_agents = []
    for pos in positions:
        params = jps.CollisionFreeSpeedModelAgentParameters(
            position=pos,
            journey_id=journey_id,
            stage_id=waypoint_id,
            v0=speed
        )
        new_agents.append(simulation.add_agent(params))

    return new_agents
