from __future__ import annotations

import math

from .geometry import get_polygon, shared_boundary_width


def compute_legacy_edge_capacity(cells, source: str, target: str) -> int:
    """
    Legacy capacity used before h3.

    It is based on the minimum area of the two connected cells.
    Keep this only for backwards compatibility.
    """
    source_polygon = get_polygon(cells[source])
    target_polygon = get_polygon(cells[target])

    return max(1, math.floor(min(source_polygon.area, target_polygon.area)))


def enrich_edges_with_capacity(
    cells,
    edges: list[tuple[str, str, float]],
) -> list[tuple[str, str, float, int]]:
    """
    Legacy edge enrichment.

    Output:
        (source, target, cost, capacity)
    """
    return [
        (
            source,
            target,
            weight,
            compute_legacy_edge_capacity(cells, source, target),
        )
        for source, target, weight in edges
    ]


def compute_node_capacity(
    cells,
    node: str,
    density_agents_per_m2: float = 2.0,
) -> int:
    """
    Compute spatial node capacity from its specific area.

    node_capacity = floor(area * density_agents_per_m2)
    """
    polygon = get_polygon(cells[node])
    return max(1, math.floor(polygon.area * density_agents_per_m2))


def compute_node_capacities(
    cells,
    density_agents_per_m2: float = 2.0,
) -> dict[str, int]:
    """
    Compute node capacities for all specific areas.

    Output:
        node_capacities = {
            "1": 50,
            "2": 25,
            ...
        }
    """
    return {
        str(node): compute_node_capacity(
            cells=cells,
            node=str(node),
            density_agents_per_m2=density_agents_per_m2,
        )
        for node in cells
    }


def compute_edge_flow_capacity(
    cells,
    source: str,
    target: str,
    flow_agents_per_meter: float = 4.0,
    fallback_edge_width: float = 1.0,
) -> int:
    """
    Compute temporal edge flow capacity.

    flow_capacity = floor(connection_width * flow_agents_per_meter)

    connection_width is the shared boundary length between the two areas.
    If no shared boundary can be measured, fallback_edge_width is used.
    """
    source_polygon = get_polygon(cells[source])
    target_polygon = get_polygon(cells[target])

    width = shared_boundary_width(source_polygon, target_polygon)

    if width <= 1e-9:
        width = fallback_edge_width

    return max(1, math.floor(width * flow_agents_per_meter))


def enrich_edges_with_flow_capacity(
    cells,
    edges: list[tuple[str, str, float]],
    flow_agents_per_meter: float = 4.0,
    fallback_edge_width: float = 1.0,
) -> list[tuple[str, str, float, int]]:
    """
    h3 edge enrichment.

    Output:
        (source, target, cost, flow_capacity)
    """
    return [
        (
            source,
            target,
            weight,
            compute_edge_flow_capacity(
                cells=cells,
                source=source,
                target=target,
                flow_agents_per_meter=flow_agents_per_meter,
                fallback_edge_width=fallback_edge_width,
            ),
        )
        for source, target, weight in edges
    ]