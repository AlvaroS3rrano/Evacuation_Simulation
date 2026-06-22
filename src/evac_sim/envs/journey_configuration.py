from __future__ import annotations

from typing import Any

import jupedsim as jps


def truncate_path_at_first_exit(
    path: list,
    exit_nodes: set[Any],
) -> list:
    """
    If a path reaches any configured exit before the final node,
    truncate it there.

    This avoids trying to use an exit as an intermediate waypoint.
    Logically, an agent is evacuated as soon as it reaches the first exit.
    """
    if not path or len(path) < 2:
        return path

    exit_nodes_as_str = {
        str(node)
        for node in exit_nodes
    }

    for index, node in enumerate(path[1:], start=1):
        if str(node) in exit_nodes_as_str:
            return path[: index + 1]

    return path


def _get_stage_id(
    stage_ids: dict[Any, int],
    node: Any,
) -> int | None:
    """
    Looks up a JuPedSim stage id while tolerating string/int node mismatches.
    """
    if node in stage_ids:
        return stage_ids[node]

    node_as_str = str(node)

    if node_as_str in stage_ids:
        return stage_ids[node_as_str]

    return None


def create_journeys_for_simulation(
    start: str,
    paths: list[list[str]],
    waypoint_ids: dict[str, int],
    exit_ids: dict[str, int],
) -> list[tuple[jps.JourneyDescription, list[str]]]:
    if not paths:
        raise ValueError(f"No valid paths found from {start}.")

    journeys: list[tuple[jps.JourneyDescription, list[str]]] = []
    skipped_reasons: list[str] = []

    for raw_path in paths:
        if raw_path is None:
            skipped_reasons.append(
                f"raw_path=None for start={start}"
            )
            continue

        if not isinstance(raw_path, (list, tuple)):
            skipped_reasons.append(
                f"raw_path is not list/tuple for start={start}: {raw_path!r}"
            )
            continue

        path = list(raw_path)

        if len(path) < 2:
            skipped_reasons.append(
                f"path too short for start={start}: path={path}"
            )
            continue

        path = truncate_path_at_first_exit(
            path,
            set(exit_ids),
        )

        if len(path) < 2:
            skipped_reasons.append(
                f"path too short after truncation for start={start}: path={path}"
            )
            continue

        exit_node = path[-1]

        exit_stage = exit_ids.get(
            exit_node,
            exit_ids.get(str(exit_node)),
        )

        if exit_stage is None:
            skipped_reasons.append(
                "missing exit stage | "
                f"start={start} | "
                f"path={path} | "
                f"exit_node={exit_node} | "
                f"available_exits={sorted(str(k) for k in exit_ids.keys())}"
            )
            continue

        intermediate_nodes = path[1:-1]

        needed_waypoints: list[int] = []
        missing_waypoint = None

        for node in intermediate_nodes:
            waypoint_stage = waypoint_ids.get(
                node,
                waypoint_ids.get(str(node)),
            )

            if waypoint_stage is None:
                missing_waypoint = node
                break

            needed_waypoints.append(waypoint_stage)

        if missing_waypoint is not None:
            skipped_reasons.append(
                "missing waypoint stage | "
                f"start={start} | "
                f"path={path} | "
                f"missing_node={missing_waypoint} | "
                f"exit_node={exit_node} | "
                f"available_exit=True | "
                f"available_waypoints={sorted(str(k) for k in waypoint_ids.keys())}"
            )
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

    if not journeys:
        raise ValueError(
            "Could not create any valid JuPedSim journey. "
            f"start={start}. "
            f"paths={paths}. "
            f"available_waypoints={sorted(str(k) for k in waypoint_ids.keys())}. "
            f"available_exits={sorted(str(k) for k in exit_ids.keys())}. "
            f"skipped_reasons={skipped_reasons}"
        )

    return journeys


def set_journeys(
    simulation: jps.Simulation,
    start: str,
    paths: list[list[str]],
    waypoint_ids: dict[str, int],
    exit_ids: dict[str, int],
) -> dict[str, list[tuple[int, list[str]]]]:
    journeys = create_journeys_for_simulation(
        start,
        paths,
        waypoint_ids,
        exit_ids,
    )

    journey_ids = [
        (simulation.add_journey(journey), path)
        for journey, path in journeys
    ]

    return {start: journey_ids} if journey_ids else {}