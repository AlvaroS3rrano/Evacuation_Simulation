from __future__ import annotations

from shapely.geometry import Point

from evac_sim.envs.layout_creation import (
    SquareCell,
    build_adaptive_square_cells,
    build_convex_navmesh_cells,
    build_greedy_square_cells,
)

from .geometry import get_cell_center, get_polygon


def load_layout_from_environment_data(environment_data):
    G = environment_data.graph

    if G is None:
        raise ValueError("environment_data is missing required key: 'graph'")

    try:
        edges = list(G.edges(data="cost"))
    except AttributeError as exc:
        raise TypeError(
            "environment_data.graph must be a networkx graph with an .edges() method"
        ) from exc

    waypoints = environment_data.waypoints

    if waypoints is None:
        raise ValueError("environment_data is missing required key: 'waypoints'")

    if not isinstance(waypoints, dict):
        raise TypeError(
            f"'waypoints' must be a dict, got {type(waypoints).__name__}"
        )

    cells = environment_data.specific_areas

    if cells is None:
        raise ValueError("environment_data is missing required key: 'specific_areas'")

    if not isinstance(cells, dict):
        raise TypeError(
            f"'specific_areas' must be a dict, got {type(cells).__name__}"
        )

    if len(cells) == 0:
        raise ValueError("'specific_areas' is empty")

    if len(edges) == 0:
        raise ValueError("Graph has no edges")

    return waypoints, edges, cells


def build_cells_from_args(args, geometry) -> dict[str, SquareCell]:
    if args.method == "greedy":
        return build_greedy_square_cells(
            walkable_area=geometry,
            base_cell_size=args.min_cell_size,
            min_square_size=args.greedy_min_square_size,
            require_full_cell=not args.greedy_center_within,
        )

    if args.method == "convex_navmesh":
        return build_convex_navmesh_cells(
            walkable_area=geometry,
            min_area=args.navmesh_min_area,
            max_area=args.navmesh_max_area,
        )

    return build_adaptive_square_cells(
        walkable_area=geometry,
        min_cell_size=args.min_cell_size,
        max_cell_size=args.max_cell_size,
        accept_partial_min_cells=args.accept_partial_min_cells,
    )


def get_largest_waypoints_from_cells(
    cells: dict[str, SquareCell],
    shrink_epsilon: float = 1e-9,
) -> dict[str, tuple[list[float], float]]:
    if shrink_epsilon < 0:
        raise ValueError("shrink_epsilon must be >= 0")

    waypoints = {}

    for cell_id, cell in cells.items():
        polygon = get_polygon(cell)
        center = get_cell_center(cell)
        point = Point(center)

        if not polygon.covers(point):
            point = polygon.representative_point()
            center = (point.x, point.y)

        radius = max(
            0.0,
            float(point.distance(polygon.boundary)) - shrink_epsilon,
        )

        waypoints[cell_id] = (
            [float(center[0]), float(center[1])],
            radius,
        )

    return waypoints