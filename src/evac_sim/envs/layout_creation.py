from __future__ import annotations

import math
from numbers import Integral
from dataclasses import dataclass
from typing import Iterable
from itertools import combinations

import networkx as nx
from shapely.geometry import (
    Point,
    Polygon,
    box,
    MultiPolygon,
    GeometryCollection,
    LineString,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import triangulate
from shapely.strtree import STRtree

try:
    from shapely import constrained_delaunay_triangles
except ImportError:
    constrained_delaunay_triangles = None


@dataclass(slots=True, frozen=True)
class SquareCell:
    cell_id: str
    polygon: Polygon
    center: tuple[float, float]
    size: float
    level: int


@dataclass(slots=True)
class BuiltGridLayout:
    waypoints: dict[str, tuple[list[float], float]]
    specific_areas: dict[str, BaseGeometry]
    graph: nx.DiGraph
    node_order: list[str]


def _extract_valid_polygon(geometry: BaseGeometry) -> Polygon | None:
    if geometry.is_empty:
        return None

    if isinstance(geometry, Polygon):
        return geometry if geometry.area > 0 else None

    if isinstance(geometry, MultiPolygon):
        polygons = [
            geom
            for geom in geometry.geoms
            if isinstance(geom, Polygon) and geom.area > 0
        ]
        if not polygons:
            return None
        return max(polygons, key=lambda p: p.area)

    if isinstance(geometry, GeometryCollection):
        polygons = [
            geom
            for geom in geometry.geoms
            if isinstance(geom, Polygon) and geom.area > 0
        ]
        if not polygons:
            return None
        return max(polygons, key=lambda p: p.area)

    return None


def _clip_cell_to_walkable_area(
    square: Polygon,
    walkable_area: BaseGeometry,
) -> Polygon | None:
    clipped = square.intersection(walkable_area)
    return _extract_valid_polygon(clipped)


def _create_square(x: float, y: float, size: float) -> Polygon:
    return box(x, y, x + size, y + size)


def _square_center(x: float, y: float, size: float) -> tuple[float, float]:
    half = size / 2.0
    return (x + half, y + half)


def _next_power_of_two_side(width: float, height: float) -> float:
    side = max(width, height)
    power = 1.0

    while power < side:
        power *= 2.0

    return power


def _subdivide_square(x: float, y: float, size: float) -> list[tuple[float, float, float]]:
    half = size / 2.0
    return [
        (x, y, half),
        (x + half, y, half),
        (x, y + half, half),
        (x + half, y + half, half),
    ]


def _should_accept_terminal_cell(
    walkable_area: BaseGeometry,
    square: Polygon,
    center: tuple[float, float],
    accept_partial_min_cells: bool,
) -> bool:
    if walkable_area.covers(square):
        return True

    if not accept_partial_min_cells:
        return False

    return walkable_area.covers(Point(center))


def _can_connect_through_walkable_area(
    cell_a: SquareCell,
    cell_b: SquareCell,
    walkable_area: BaseGeometry,
    tolerance: float = 1e-9,
) -> bool:
    line = LineString([cell_a.center, cell_b.center])
    buffered = line.buffer(tolerance)
    return walkable_area.covers(line) or walkable_area.covers(buffered)


def build_adaptive_square_cells(
    walkable_area: BaseGeometry,
    min_cell_size: float,
    max_cell_size: float | None = None,
    accept_partial_min_cells: bool = False,
) -> dict[str, SquareCell]:
    if min_cell_size <= 0:
        raise ValueError("min_cell_size must be > 0")

    minx, miny, maxx, maxy = walkable_area.bounds
    width = maxx - minx
    height = maxy - miny

    if width == 0 or height == 0:
        raise ValueError("walkable_area must have non-zero width and height")

    root_size = _next_power_of_two_side(width, height)

    if max_cell_size is not None:
        if max_cell_size <= 0:
            raise ValueError("max_cell_size must be > 0")

        root_size = min(root_size, max_cell_size)

        if root_size < min_cell_size:
            raise ValueError("max_cell_size must be >= min_cell_size")

    cells: dict[str, SquareCell] = {}
    next_id = 1

    stack: list[tuple[float, float, float, int]] = [(minx, miny, root_size, 0)]

    while stack:
        x, y, size, level = stack.pop()
        square = _create_square(x, y, size)

        if not walkable_area.intersects(square):
            continue

        center = _square_center(x, y, size)

        if walkable_area.covers(square):
            clipped = square
            clipped_center = (clipped.centroid.x, clipped.centroid.y)

            cell_id = str(next_id)
            cells[cell_id] = SquareCell(
                cell_id=cell_id,
                polygon=clipped,
                center=clipped_center,
                size=size,
                level=level,
            )
            next_id += 1
            continue

        if size <= min_cell_size:
            if _should_accept_terminal_cell(
                walkable_area=walkable_area,
                square=square,
                center=center,
                accept_partial_min_cells=accept_partial_min_cells,
            ):
                clipped = _clip_cell_to_walkable_area(square, walkable_area)

                if clipped is not None:
                    clipped_center = (clipped.centroid.x, clipped.centroid.y)

                    cell_id = str(next_id)
                    cells[cell_id] = SquareCell(
                        cell_id=cell_id,
                        polygon=clipped,
                        center=clipped_center,
                        size=size,
                        level=level,
                    )
                    next_id += 1

            continue

        for child_x, child_y, child_size in _subdivide_square(x, y, size):
            stack.append((child_x, child_y, child_size, level + 1))

    return cells


def get_waypoints_from_cells(
    cells: dict[str, SquareCell],
    radius: float | None = None,
    radius_ratio: float = 0.25,
    min_radius: float = 0.10,
    max_radius: float | None = None,
) -> dict[str, tuple[list[float], float]]:
    """
    Build waypoints from the center of each cell.

    For convex_navmesh, limiting the waypoint radius is important because agents
    complete a waypoint as soon as they enter its circular area.
    """
    if radius is not None and radius <= 0:
        raise ValueError("radius must be > 0")

    if radius is None and radius_ratio <= 0:
        raise ValueError("radius_ratio must be > 0")

    if min_radius <= 0:
        raise ValueError("min_radius must be > 0")

    if max_radius is not None and max_radius <= 0:
        raise ValueError("max_radius must be > 0")

    if max_radius is not None and max_radius < min_radius:
        raise ValueError("max_radius must be >= min_radius")

    waypoints: dict[str, tuple[list[float], float]] = {}

    for cell_id, cell in cells.items():
        waypoint_radius = radius if radius is not None else cell.size * radius_ratio

        if max_radius is not None:
            waypoint_radius = min(waypoint_radius, max_radius)

        waypoint_radius = max(waypoint_radius, min_radius)

        waypoints[cell_id] = (
            [cell.center[0], cell.center[1]],
            waypoint_radius,
        )

    return waypoints


def filter_cells_by_size(
    cells: dict[str, SquareCell],
    min_size: float | None = None,
    max_size: float | None = None,
) -> dict[str, SquareCell]:
    result: dict[str, SquareCell] = {}

    for cell_id, cell in cells.items():
        if min_size is not None and cell.size < min_size:
            continue

        if max_size is not None and cell.size > max_size:
            continue

        result[cell_id] = cell

    return result


def iter_cell_polygons(cells: dict[str, SquareCell]) -> Iterable[Polygon]:
    return (cell.polygon for cell in cells.values())


def _build_walkable_mask(
    walkable_area: BaseGeometry,
    base_cell_size: float,
    require_full_cell: bool = True,
    min_intersection_ratio: float = 0.0,
) -> tuple[list[list[bool]], float, float, int, int]:
    minx, miny, maxx, maxy = walkable_area.bounds

    rows = math.ceil((maxy - miny) / base_cell_size)
    cols = math.ceil((maxx - minx) / base_cell_size)

    if rows <= 0 or cols <= 0:
        raise ValueError("Invalid grid size derived from walkable_area and base_cell_size")

    mask = [[False for _ in range(cols)] for _ in range(rows)]
    full_area = base_cell_size * base_cell_size

    for row in range(rows):
        for col in range(cols):
            x = minx + col * base_cell_size
            y = miny + row * base_cell_size
            cell = _create_square(x, y, base_cell_size)

            if require_full_cell:
                mask[row][col] = walkable_area.covers(cell)
            else:
                inter = cell.intersection(walkable_area)

                if not inter.is_empty and inter.area > 0:
                    ratio = inter.area / full_area
                    mask[row][col] = ratio >= min_intersection_ratio
                else:
                    mask[row][col] = False

    return mask, minx, miny, rows, cols


def _compute_max_square_dp(mask: list[list[bool]]) -> list[list[int]]:
    rows = len(mask)
    cols = len(mask[0]) if rows > 0 else 0

    dp = [[0 for _ in range(cols)] for _ in range(rows)]

    for row in range(rows - 1, -1, -1):
        for col in range(cols - 1, -1, -1):
            if not mask[row][col]:
                dp[row][col] = 0
            elif row == rows - 1 or col == cols - 1:
                dp[row][col] = 1
            else:
                dp[row][col] = 1 + min(
                    dp[row + 1][col],
                    dp[row][col + 1],
                    dp[row + 1][col + 1],
                )

    return dp


def _mark_square_used(
    mask: list[list[bool]],
    top_row: int,
    left_col: int,
    side: int,
) -> None:
    for r in range(top_row, top_row + side):
        for c in range(left_col, left_col + side):
            mask[r][c] = False


def build_greedy_square_cells(
    walkable_area: BaseGeometry,
    base_cell_size: float,
    min_square_size: float | None = None,
    require_full_cell: bool = True,
) -> dict[str, SquareCell]:
    if base_cell_size <= 0:
        raise ValueError("base_cell_size must be > 0")

    if min_square_size is None:
        min_square_size = base_cell_size

    if min_square_size <= 0:
        raise ValueError("min_square_size must be > 0")

    mask, minx, miny, rows, cols = _build_walkable_mask(
        walkable_area=walkable_area,
        base_cell_size=base_cell_size,
        require_full_cell=require_full_cell,
        min_intersection_ratio=0.01 if not require_full_cell else 1.0,
    )

    min_side_cells = max(1, round(min_square_size / base_cell_size))

    cells: dict[str, SquareCell] = {}
    next_id = 1

    while True:
        dp = _compute_max_square_dp(mask)

        best_row = -1
        best_col = -1
        best_side = 0

        for row in range(rows):
            for col in range(cols):
                side = dp[row][col]

                if side > best_side:
                    best_side = side
                    best_row = row
                    best_col = col

        if best_side < min_side_cells:
            break

        x = minx + best_col * base_cell_size
        y = miny + best_row * base_cell_size
        size = best_side * base_cell_size

        square = _create_square(x, y, size)
        clipped = _clip_cell_to_walkable_area(square, walkable_area)

        if clipped is None:
            _mark_square_used(mask, best_row, best_col, best_side)
            continue

        center = (clipped.centroid.x, clipped.centroid.y)

        cell_id = str(next_id)
        cells[cell_id] = SquareCell(
            cell_id=cell_id,
            polygon=clipped,
            center=center,
            size=size,
            level=0,
        )
        next_id += 1

        _mark_square_used(mask, best_row, best_col, best_side)

    return cells


def _iter_polygon_parts(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []

    if isinstance(geometry, Polygon):
        return [geometry] if geometry.area > 0 else []

    if isinstance(geometry, MultiPolygon):
        return [
            poly
            for poly in geometry.geoms
            if isinstance(poly, Polygon) and poly.area > 0
        ]

    if isinstance(geometry, GeometryCollection):
        return [
            geom
            for geom in geometry.geoms
            if isinstance(geom, Polygon) and geom.area > 0
        ]

    return []


def _is_convex_polygon(
    polygon: Polygon,
    tolerance: float = 1e-9,
) -> bool:
    if polygon.is_empty or polygon.area <= tolerance:
        return False

    convex_hull = polygon.convex_hull
    return abs(convex_hull.area - polygon.area) <= tolerance


def _triangulate_walkable_polygon(polygon: Polygon) -> list[Polygon]:
    if constrained_delaunay_triangles is not None:
        triangles_geom = constrained_delaunay_triangles(polygon)
        raw_triangles = _iter_polygon_parts(triangles_geom)
    else:
        raw_triangles = triangulate(polygon)

    triangles: list[Polygon] = []

    for triangle in raw_triangles:
        clipped = triangle.intersection(polygon)

        for part in _iter_polygon_parts(clipped):
            if part.area <= 1e-9:
                continue

            if not polygon.covers(part.representative_point()):
                continue

            if not _is_convex_polygon(part):
                continue

            triangles.append(part)

    return triangles

def _split_triangle_into_four(triangle: Polygon) -> list[Polygon]:
    coords = list(triangle.exterior.coords)[:-1]

    if len(coords) != 3:
        return [triangle]

    a, b, c = coords

    ab = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    bc = ((b[0] + c[0]) / 2.0, (b[1] + c[1]) / 2.0)
    ca = ((c[0] + a[0]) / 2.0, (c[1] + a[1]) / 2.0)

    return [
        Polygon([a, ab, ca]),
        Polygon([ab, b, bc]),
        Polygon([ca, bc, c]),
        Polygon([ab, bc, ca]),
    ]


def _subdivide_large_triangles(
    triangles: list[Polygon],
    max_area: float,
) -> list[Polygon]:
    result: list[Polygon] = []
    stack = list(triangles)

    while stack:
        triangle = stack.pop()

        if triangle.area <= max_area:
            result.append(triangle)
            continue

        stack.extend(_split_triangle_into_four(triangle))

    return result


def build_convex_navmesh_cells(
    walkable_area: BaseGeometry,
    min_area: float = 0.02,
    max_area: float | None = 0.35,
) -> dict[str, SquareCell]:
    if min_area <= 0:
        raise ValueError("min_area must be > 0")

    if max_area is not None and max_area <= min_area:
        raise ValueError("max_area must be greater than min_area")

    cells: dict[str, SquareCell] = {}
    next_id = 1

    for polygon in _iter_polygon_parts(walkable_area):
        triangles = _triangulate_walkable_polygon(polygon)

        if max_area is not None:
            triangles = _subdivide_large_triangles(
                triangles=triangles,
                max_area=max_area,
            )

        for triangle in triangles:
            if triangle.area < min_area:
                continue

            if not polygon.covers(triangle.representative_point()):
                continue

            point = triangle.representative_point()
            cell_id = str(next_id)

            cells[cell_id] = SquareCell(
                cell_id=cell_id,
                polygon=triangle,
                center=(float(point.x), float(point.y)),
                size=math.sqrt(float(triangle.area)),
                level=0,
            )
            next_id += 1

    return cells


def compute_distance(
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _shared_boundary_length(
    polygon_a: BaseGeometry,
    polygon_b: BaseGeometry,
) -> float:
    boundary_intersection = polygon_a.boundary.intersection(polygon_b.boundary)

    if boundary_intersection.is_empty:
        return 0.0

    if boundary_intersection.geom_type == "LineString":
        return float(boundary_intersection.length)

    if boundary_intersection.geom_type == "MultiLineString":
        return float(sum(line.length for line in boundary_intersection.geoms))

    if boundary_intersection.geom_type == "GeometryCollection":
        return float(
            sum(
                geom.length
                for geom in boundary_intersection.geoms
                if geom.geom_type in {"LineString", "LinearRing"}
            )
        )

    return 0.0


def _are_neighbor_cells(
    polygon_a: BaseGeometry,
    polygon_b: BaseGeometry,
    min_shared_length: float = 1e-9,
    distance_tolerance: float = 1e-9,
) -> bool:
    if polygon_a.is_empty or polygon_b.is_empty:
        return False

    return _shared_boundary_length(polygon_a, polygon_b) > min_shared_length


def ensure_graph_connectivity(
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
    walkable_area: BaseGeometry,
) -> list[tuple[str, str, float]]:
    if not cells:
        return edges

    undirected = nx.Graph()

    for cell_id in cells:
        undirected.add_node(cell_id)

    for source, target, weight in edges:
        undirected.add_edge(source, target, weight=weight)

    components = list(nx.connected_components(undirected))

    if len(components) <= 1:
        return edges

    edge_map: set[tuple[str, str]] = {(s, t) for s, t, _ in edges}
    new_edges = list(edges)

    while True:
        components = list(nx.connected_components(undirected))

        if len(components) <= 1:
            break

        best_pair = None
        best_distance = float("inf")

        for comp_a, comp_b in combinations(components, 2):
            for node_a in comp_a:
                for node_b in comp_b:
                    cell_a = cells[node_a]
                    cell_b = cells[node_b]

                    if not _can_connect_through_walkable_area(
                        cell_a,
                        cell_b,
                        walkable_area,
                    ):
                        continue

                    dist = compute_distance(cell_a.center, cell_b.center)

                    if dist < best_distance:
                        best_distance = dist
                        best_pair = (node_a, node_b, dist)

        if best_pair is None:
            break

        a, b, w = best_pair

        if (a, b) not in edge_map:
            new_edges.append((a, b, w))
            edge_map.add((a, b))

        if (b, a) not in edge_map:
            new_edges.append((b, a, w))
            edge_map.add((b, a))

        undirected.add_edge(a, b, weight=w)

    return new_edges


def build_bidirectional_weighted_edges(
    cells: dict[str, SquareCell],
    walkable_area: BaseGeometry | None = None,
    min_shared_length: float = 1e-9,
) -> list[tuple[str, str, float]]:
    if not cells:
        return []

    cell_items = list(cells.items())
    cell_ids = [cell_id for cell_id, _ in cell_items]
    polygons = [cell.polygon for _, cell in cell_items]

    tree = STRtree(polygons)

    edges: list[tuple[str, str, float]] = []
    seen_undirected_pairs: set[tuple[str, str]] = set()

    for i, (cell_id, cell) in enumerate(cell_items):
        candidates = tree.query(cell.polygon)

        for candidate in candidates:
            if isinstance(candidate, Integral):
                j = int(candidate)
            else:
                try:
                    j = polygons.index(candidate)
                except ValueError:
                    continue

            if i == j:
                continue

            other_id = cell_ids[j]
            other_cell = cells[other_id]

            pair = tuple(sorted((cell_id, other_id)))

            if pair in seen_undirected_pairs:
                continue

            if not _are_neighbor_cells(
                cell.polygon,
                other_cell.polygon,
                min_shared_length=min_shared_length,
            ):
                continue

            weight = compute_distance(cell.center, other_cell.center)

            edges.append((cell_id, other_id, weight))
            edges.append((other_id, cell_id, weight))
            seen_undirected_pairs.add(pair)

    if walkable_area is not None:
        edges = ensure_graph_connectivity(cells, edges, walkable_area)

    return edges
