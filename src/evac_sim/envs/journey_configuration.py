from __future__ import annotations

import jupedsim as jps


def create_journeys_for_simulation(
    start: str,
    paths: list[list[str]],
    waypoint_ids: dict[str, int],
    exit_ids: dict[str, int],
) -> list[tuple[jps.JourneyDescription, list[str]]]:
    if not paths:
        raise ValueError(f"No valid paths found from {start}.")

    journeys: list[tuple[jps.JourneyDescription, list[str]]] = []

    for path in paths:
        if len(path) < 2:
            continue

        exit_node = path[-1]
        exit_stage = exit_ids.get(exit_node)
        if exit_stage is None:
            continue

        intermediate_nodes = path[1:-1]
        try:
            needed_waypoints = [waypoint_ids[node] for node in intermediate_nodes]
        except KeyError:
            continue

        stages = [*needed_waypoints, exit_stage]
        journey = jps.JourneyDescription(stages)

        for idx, waypoint in enumerate(needed_waypoints):
            next_stage = stages[idx + 1]
            journey.set_transition_for_stage(
                waypoint,
                jps.Transition.create_fixed_transition(next_stage),
            )

        journeys.append((journey, path))

    return journeys


def set_journeys(
    simulation: jps.Simulation,
    start: str,
    paths: list[list[str]],
    waypoint_ids: dict[str, int],
    exit_ids: dict[str, int],
) -> dict[str, list[tuple[int, list[str]]]]:
    journeys = create_journeys_for_simulation(start, paths, waypoint_ids, exit_ids)

    journey_ids = [
        (simulation.add_journey(journey), path)
        for journey, path in journeys
    ]
    return {start: journey_ids} if journey_ids else {}