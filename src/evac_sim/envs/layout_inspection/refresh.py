from __future__ import annotations

import math

import networkx as nx
from shapely.geometry import LineString


def compute_waypoint_distance(
    waypoints: dict[str, tuple[list[float], float]],
    source: str,
    target: str,
) -> float:
    source_point = waypoints[source][0]
    target_point = waypoints[target][0]

    return math.hypot(
        target_point[0] - source_point[0],
        target_point[1] - source_point[1],
    )


def can_connect_waypoints_through_walkable_area(
    waypoints: dict[str, tuple[list[float], float]],
    source: str,
    target: str,
    walkable_geometry,
    tolerance: float = 1e-9,
) -> bool:
    source_point = waypoints[source][0]
    target_point = waypoints[target][0]

    line = LineString([source_point, target_point])
    buffered = line.buffer(tolerance)

    return walkable_geometry.covers(line) or walkable_geometry.covers(buffered)


def recalculate_edge_distances(
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
) -> list[tuple[str, str, float]]:
    recalculated_edges = []

    for source, target, _ in edges:
        if source not in waypoints or target not in waypoints:
            print(
                f"[WARN] Skipping edge {source}->{target}: "
                "source or target waypoint does not exist"
            )
            continue

        recalculated_edges.append(
            (
                source,
                target,
                compute_waypoint_distance(waypoints, source, target),
            )
        )

    return recalculated_edges


def connect_disconnected_current_edges(
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
    walkable_geometry,
) -> list[tuple[str, str, float]]:
    if not waypoints:
        return edges

    undirected = nx.Graph()
    undirected.add_nodes_from(waypoints)

    existing_pairs = set()

    for source, target, weight in edges:
        undirected.add_edge(source, target, weight=weight)
        existing_pairs.add((source, target))

    refreshed_edges = list(edges)

    while True:
        components = list(nx.connected_components(undirected))

        if len(components) <= 1:
            break

        best_connection = None
        best_distance = float("inf")

        for index_a, component_a in enumerate(components):
            for component_b in components[index_a + 1:]:
                for source in component_a:
                    for target in component_b:
                        if not can_connect_waypoints_through_walkable_area(
                            waypoints=waypoints,
                            source=source,
                            target=target,
                            walkable_geometry=walkable_geometry,
                        ):
                            continue

                        distance = compute_waypoint_distance(
                            waypoints=waypoints,
                            source=source,
                            target=target,
                        )

                        if distance < best_distance:
                            best_distance = distance
                            best_connection = (source, target, distance)

        if best_connection is None:
            unresolved = [
                sorted(
                    component,
                    key=lambda node: int(node) if str(node).isdigit() else str(node),
                )
                for component in components
            ]

            print(
                "[WARN] Some current-layout components could not be connected "
                f"without crossing obstacles: {unresolved}"
            )
            break

        source, target, distance = best_connection

        if (source, target) not in existing_pairs:
            refreshed_edges.append((source, target, distance))
            existing_pairs.add((source, target))

        if (target, source) not in existing_pairs:
            refreshed_edges.append((target, source, distance))
            existing_pairs.add((target, source))

        undirected.add_edge(source, target, weight=distance)

        print(
            f"[INFO] Added connection {source}<->{target} "
            f"with distance={distance:.6f}"
        )

    return refreshed_edges


def refresh_current_edges(
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
    walkable_geometry,
) -> list[tuple[str, str, float]]:
    recalculated_edges = recalculate_edge_distances(
        edges=edges,
        waypoints=waypoints,
    )

    return connect_disconnected_current_edges(
        edges=recalculated_edges,
        waypoints=waypoints,
        walkable_geometry=walkable_geometry,
    )