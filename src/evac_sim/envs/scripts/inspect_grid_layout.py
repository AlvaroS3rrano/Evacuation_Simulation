from __future__ import annotations

import argparse
import math
from collections import Counter

import matplotlib.pyplot as plt
import networkx as nx
import pedpy
from matplotlib.patches import Circle
from shapely.geometry import LineString, Point, Polygon

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    SquareCell,
    build_adaptive_square_cells,
    build_greedy_square_cells,
    build_convex_navmesh_cells,
    get_waypoints_from_cells,
    build_bidirectional_weighted_edges,
)



def _get_polygon(cell_or_polygon) -> Polygon:
    polygon = getattr(cell_or_polygon, "polygon", cell_or_polygon)
    if not isinstance(polygon, Polygon):
        raise TypeError(f"Expected Polygon-compatible cell, got {type(polygon).__name__}")
    return polygon


def compute_edge_capacity(cells, source: str, target: str) -> int:
    source_polygon = _get_polygon(cells[source])
    target_polygon = _get_polygon(cells[target])

    source_area = source_polygon.area
    target_area = target_polygon.area

    return max(1, math.floor(min(source_area, target_area)))


def enrich_edges_with_capacity(cells, edges: list[tuple[str, str, float]]) -> list[tuple[str, str, float, int]]:
    return [
        (source, target, weight, compute_edge_capacity(cells, source, target))
        for source, target, weight in edges
    ]


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


def _can_connect_waypoints_through_walkable_area(
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
    recalculated_edges: list[tuple[str, str, float]] = []

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
    """
    Keep the existing current-layout edges and add bidirectional edges between
    disconnected components when the straight segment between two waypoints
    remains inside the walkable area.
    """
    if not waypoints:
        return edges

    undirected = nx.Graph()
    undirected.add_nodes_from(waypoints)

    existing_pairs: set[tuple[str, str]] = set()

    for source, target, weight in edges:
        undirected.add_edge(source, target, weight=weight)
        existing_pairs.add((source, target))

    refreshed_edges = list(edges)

    while True:
        components = list(nx.connected_components(undirected))

        if len(components) <= 1:
            break

        best_connection: tuple[str, str, float] | None = None
        best_distance = float("inf")

        for index_a, component_a in enumerate(components):
            for component_b in components[index_a + 1:]:
                for source in component_a:
                    for target in component_b:
                        if not _can_connect_waypoints_through_walkable_area(
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
                sorted(component, key=lambda node: int(node) if node.isdigit() else node)
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

def _get_cell_center(cell_or_polygon):
    if hasattr(cell_or_polygon, "center"):
        return cell_or_polygon.center

    polygon = getattr(cell_or_polygon, "polygon", cell_or_polygon)
    centroid = polygon.centroid
    return (centroid.x, centroid.y)


def get_largest_waypoints_from_cells(
    cells: dict[str, SquareCell],
    shrink_epsilon: float = 1e-9,
) -> dict[str, tuple[list[float], float]]:
    """
    Build waypoints whose acceptance radius is the largest circle centered in the
    cell that remains inside the cell polygon.

    Since waypoints store radius, not diameter, the largest accepted radius is
    the distance from the waypoint center to the specific area's boundary.
    """
    if shrink_epsilon < 0:
        raise ValueError("shrink_epsilon must be >= 0")

    waypoints: dict[str, tuple[list[float], float]] = {}

    for cell_id, cell in cells.items():
        polygon = _get_polygon(cell)
        center = _get_cell_center(cell)
        point = Point(center)

        if not polygon.covers(point):
            point = polygon.representative_point()
            center = (point.x, point.y)

        radius = max(0.0, float(point.distance(polygon.boundary)) - shrink_epsilon)

        waypoints[cell_id] = (
            [float(center[0]), float(center[1])],
            radius,
        )

    return waypoints

def draw_waypoint(
    ax,
    waypoint,
    distance,
    idx,
    show_node_id: bool = True,
    node_label_color: str = "darkred",
) -> None:
    ax.plot(waypoint[0], waypoint[1], "ro")

    if show_node_id:
        ax.annotate(
            f"{idx}",
            (waypoint[0], waypoint[1]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8),
            zorder=10,
        )

    circle = Circle(
        (waypoint[0], waypoint[1]),
        distance,
        fc="red",
        ec="red",
        alpha=0.1,
    )
    ax.add_patch(circle)


def draw_cell(
    ax,
    polygon,
    cell_id: str | None = None,
    show_cell_id: bool = False,
    show_cell_size: bool = False,
    cell_size: float | None = None,
) -> None:
    x, y = polygon.exterior.xy
    ax.plot(x, y, linewidth=0.7, color="black", alpha=0.8, zorder=2)

    centroid = polygon.centroid

    if show_cell_id and cell_id is not None:
        ax.annotate(
            str(cell_id),
            (centroid.x, centroid.y),
            textcoords="offset points",
            xytext=(0, 0),
            ha="center",
            va="center",
            fontsize=7,
            color="navy",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7),
            zorder=3,
        )

    if show_cell_size and cell_size is not None:
        ax.annotate(
            f"{cell_size:g}",
            (centroid.x, centroid.y),
            textcoords="offset points",
            xytext=(0, -12),
            ha="center",
            va="center",
            fontsize=7,
            color="dimgray",
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7),
            zorder=3,
        )


def draw_edges(
    ax,
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
    show_edge_weights: bool = False,
) -> None:
    drawn_pairs: set[tuple[str, str]] = set()

    for source, target, weight in edges:
        pair = tuple(sorted((source, target)))
        if pair in drawn_pairs:
            continue

        p1 = _get_cell_center(cells[source])
        p2 = _get_cell_center(cells[target])

        ax.plot(
            [p1[0], p2[0]],
            [p1[1], p2[1]],
            linewidth=0.6,
            alpha=0.5,
            color="gray",
            zorder=1,
        )

        if show_edge_weights:
            mx = (p1[0] + p2[0]) / 2
            my = (p1[1] + p2[1]) / 2
            ax.annotate(
                f"{weight:.2f}",
                (mx, my),
                textcoords="offset points",
                xytext=(0, 0),
                ha="center",
                va="center",
                fontsize=6,
                color="darkgreen",
                bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.7),
                zorder=2,
            )

        drawn_pairs.add(pair)


def print_cell_statistics(cells) -> None:
    size_counter = Counter()
    level_counter = Counter()

    has_structured_cells = False

    for cell in cells.values():
        size = getattr(cell, "size", None)
        level = getattr(cell, "level", None)

        if size is not None:
            size_counter[size] += 1
            has_structured_cells = True

        if level is not None:
            level_counter[level] += 1
            has_structured_cells = True

    if not has_structured_cells:
        print("Cell statistics are not available for current layout source.")
        return

    print("Cell statistics by size:")
    for size in sorted(size_counter):
        print(f"  size={size}: {size_counter[size]}")

    print("Cell statistics by level:")
    for level in sorted(level_counter):
        print(f"  level={level}: {level_counter[level]}")


def print_waypoints_python(waypoints: dict[str, tuple[list[float], float]]) -> None:
    print("waypoints = {")
    for key in sorted(waypoints, key=lambda x: int(x) if x.isdigit() else x):
        point, radius = waypoints[key]
        print(f'    "{key}": ({point}, {radius}),')
    print("}")


def print_edges_python(edges: list[tuple[str, str, float, int]]) -> None:
    print("edges = [")
    for source, target, weight, capacity in edges:
        print(f'    ("{source}", "{target}", {weight}, {capacity}),')
    print("]")


def print_specific_areas_python(cells) -> None:
    print("specific_areas = {")

    for key in sorted(cells, key=lambda x: int(x) if str(x).isdigit() else str(x)):
        cell_or_polygon = cells[key]

        polygon = getattr(cell_or_polygon, "polygon", cell_or_polygon)

        if not isinstance(polygon, Polygon):
            print(f'    "{key}": {polygon.wkt},')
            continue

        coords = list(polygon.exterior.coords)[:-1]
        coords_str = ", ".join(
            f"({int(x) if float(x).is_integer() else x}, {int(y) if float(y).is_integer() else y})"
            for x, y in coords
        )

        print(f'    "{key}": Polygon([{coords_str}]),')

    print("}")

def print_layout_summary(
    args: argparse.Namespace,
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
) -> None:
    print(f"Environment: {args.env}")
    print(f"Strategy: {args.method}")
    print(f"Waypoint radius mode: {args.waypoint_radius_mode}")

    if args.layout_source == "current":
        print(f"Refresh current edges: {args.refresh_current_edges}")

    print(f"Minimum cell size: {args.min_cell_size}")

    if args.method == "greedy":
        print(f"Greedy minimum square size: {args.greedy_min_square_size}")
        print(f"Greedy require full cell: {not args.greedy_center_within}")
    else:
        print(f"Maximum cell size: {args.max_cell_size}")
        print(f"Accept partial min cells: {args.accept_partial_min_cells}")

    print(f"Cells generated: {len(cells)}")
    print(f"Waypoints/nodes generated: {len(waypoints)}")
    print(f"Directed weighted edges generated: {len(edges)}")
    print(f"Undirected connections generated: {len(edges) // 2}")
    print_cell_statistics(cells)


def build_cells_from_args(
    args: argparse.Namespace,
    geometry,
) -> dict[str, SquareCell]:
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

def _build_plot_title(
    args: argparse.Namespace,
    cells,
    waypoints: dict[str, tuple[list[float], float]],
    edges: list[tuple[str, str, float]],
) -> str:
    if args.layout_source == "current":
        return (
            f"Current layout inspection - env={args.env}, "
            f"areas={len(cells)}, nodes={len(waypoints)}, edges={len(edges)}"
        )

    return (
        f"Grid layout / graph inspection - env={args.env}, method={args.method}, "
        f"min_cell_size={args.min_cell_size}, cells={len(cells)}, "
        f"nodes={len(waypoints)}, edges={len(edges)}"
    )

def plot_layout(
    walkable_area,
    cells,
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
    args: argparse.Namespace,
) -> None:
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(24, 16))
    ax.set_aspect("equal")

    pedpy.plot_walkable_area(walkable_area=walkable_area, axes=ax)

    # specific areas / cells
    for cell_id, cell in cells.items():
        polygon = getattr(cell, "polygon", cell)
        cell_size = getattr(cell, "size", None)

        draw_cell(
            ax=ax,
            polygon=polygon,
            cell_id=cell_id,
            show_cell_id=args.show_cell_id,
            show_cell_size=args.show_cell_size,
            cell_size=cell_size,
        )

    # graph edges
    draw_edges(ax, cells, edges, show_edge_weights=args.show_edge_weights)

    # graph nodes = waypoints
    for node_id, (point, distance) in waypoints.items():
        draw_waypoint(
            ax=ax,
            waypoint=point,
            distance=distance,
            idx=node_id,
            show_node_id=args.show_node_id,
        )

    ax.set_title(_build_plot_title(args, cells, waypoints, edges))

    plt.tight_layout()
    plt.show()

def _load_layout_from_environment_data(environment_data):

    G = environment_data.graph
    if G is None:
        raise ValueError("environment_data is missing required key: 'graph'")

    try:
        edges = list(G.edges(data="cost"))
    except AttributeError:
        raise TypeError(
            "environment_data['graph'] must be a networkx graph with an .edges() method"
        )

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect grid layout: walkable area, specific areas, waypoints/nodes and edges"
    )
    parser.add_argument("--env", default="corridor", help="Environment name")

    parser.add_argument(
        "--method",
        type=str,
        default="greedy",
        choices=["greedy", "quadtree", "convex_navmesh"],
        help="Cell generation strategy",
    )

    parser.add_argument(
        "--layout-source",
        choices=["computed", "current"],
        default="computed",
        help="Source of the grid layout: 'computed' (default) or 'current' (from environment_data)",
    )

    parser.add_argument(
        "--refresh-current-edges",
        action="store_true",
        help=(
            "Only with --layout-source current: keep current edges, recalculate "
            "their distances from waypoint coordinates, and try to connect "
            "disconnected components if a straight walkable segment exists"
        ),
    )

    parser.add_argument(
        "--min-cell-size",
        type=float,
        default=1.0,
        help="Minimum allowed square cell size for quadtree, or base cell size for greedy",
    )

    parser.add_argument(
        "--max-cell-size",
        type=float,
        default=None,
        help="Optional maximum initial cell size for quadtree",
    )

    parser.add_argument(
        "--accept-partial-min-cells",
        action="store_true",
        help="For quadtree: accept partially intersecting min cells if their center is inside",
    )

    parser.add_argument(
        "--greedy-min-square-size",
        type=float,
        default=None,
        help="For greedy: minimum square size to keep. Defaults to --min-cell-size",
    )

    parser.add_argument(
        "--greedy-center-within",
        action="store_true",
        help="For greedy: accept base cells by center-inside instead of full-cell coverage",
    )

    parser.add_argument(
        "--waypoint-radius-mode",
        type=str,
        default="largest",
        choices=["largest", "ratio"],
        help=(
            "For --layout-source computed: 'largest' creates each waypoint with "
            "the maximum radius accepted by its specific area; 'ratio' keeps the "
            "previous cell-size ratio behavior"
        ),
    )

    parser.add_argument(
        "--radius",
        type=float,
        default=None,
        help="Fixed waypoint radius. If omitted, radius_ratio is used",
    )

    parser.add_argument(
        "--radius-ratio",
        type=float,
        default=0.25,
        help="Waypoint radius as a fraction of the cell size when --radius is not used",
    )

    parser.add_argument(
        "--show-node-id",
        action="store_true",
        help="Show graph node ids next to waypoint centers",
    )

    parser.add_argument(
        "--show-cell-id",
        action="store_true",
        help="Show cell/specific area ids at the center of each cell",
    )

    parser.add_argument(
        "--show-cell-size",
        action="store_true",
        help="Show the side length of each cell",
    )

    parser.add_argument(
        "--show-edge-weights",
        action="store_true",
        help="Show edge weights",
    )

    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Do not display the plot",
    )

    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print layout summary information",
    )

    parser.add_argument(
        "--print-waypoints",
        action="store_true",
        help="Print waypoints/nodes as Python dictionary",
    )

    parser.add_argument(
        "--print-edges",
        action="store_true",
        help="Print edges as Python list",
    )

    parser.add_argument(
        "--print-specific-areas",
        action="store_true",
        help="Print cell polygons as Python dictionary",
    )

    parser.add_argument(
        "--navmesh-min-area",
        type=float,
        default=1,
        help="Minimum triangle area for convex_navmesh",
    )

    parser.add_argument(
        "--navmesh-max-area",
        type=float,
        default=5,
        help="Maximum triangle area for convex_navmesh before subdivision",
    )

    parser.add_argument(
        "--max-waypoint-radius",
        type=float,
        default=0.35,
        help="Maximum waypoint acceptance radius",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    env = select_environment(args.env)
    walkable_area = env.walkable_area

    geometry = walkable_area.polygon

    if args.layout_source == "computed":
        cells = build_cells_from_args(args, geometry)

        edges = build_bidirectional_weighted_edges(cells, walkable_area=geometry)

        if args.waypoint_radius_mode == "largest":
            waypoints = get_largest_waypoints_from_cells(cells)
        else:
            waypoints = get_waypoints_from_cells(
                cells,
                radius=args.radius,
                radius_ratio=args.radius_ratio,
                min_radius=0.10,
                max_radius=args.max_waypoint_radius,
            )
    elif args.layout_source == "current":
        waypoints, edges, cells = _load_layout_from_environment_data(env)

        if args.refresh_current_edges:
            edges = refresh_current_edges(
                edges=edges,
                waypoints=waypoints,
                walkable_geometry=geometry,
            )

    should_print_summary = args.print_summary or (
        not args.print_waypoints and not args.print_edges and not args.print_specific_areas
    )

    if should_print_summary:
        print_layout_summary(args, cells, edges, waypoints)

    if args.print_waypoints:
        print_waypoints_python(waypoints)

    if args.print_edges:
        print_edges_python(enrich_edges_with_capacity(cells, edges))

    if args.print_specific_areas:
        print_specific_areas_python(cells)

    if not args.no_plot:
        plot_layout(
            walkable_area=walkable_area,
            cells=cells,
            edges=edges,
            waypoints=waypoints,
            args=args,
        )


if __name__ == "__main__":
    main()