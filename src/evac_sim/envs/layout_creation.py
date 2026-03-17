from __future__ import annotations

import math
from numbers import Integral
from dataclasses import dataclass
from typing import Iterable

import networkx as nx
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree


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


def build_adaptive_square_cells(
    walkable_area: BaseGeometry,
    min_cell_size: float,
    max_cell_size: float | None = None,
    accept_partial_min_cells: bool = False,
) -> dict[str, SquareCell]:
    """
    Build an adaptive square decomposition of a walkable area.

    Strategy:
    - Start from the largest square that covers the walkable area bounds.
    - Accept squares that are fully covered by the walkable area.
    - Discard squares that do not intersect the walkable area.
    - Subdivide partially intersecting squares until `min_cell_size` is reached.
    - Optionally accept partial cells at the minimum size if their center lies inside.

    Parameters
    ----------
    walkable_area:
        Geometry representing the walkable area.
    min_cell_size:
        Minimum allowed square side length.
    max_cell_size:
        Optional maximum initial square size. If not provided, the smallest power-of-two
        square covering the whole bounding box is used.
    accept_partial_min_cells:
        If True, partially intersecting cells at the minimum size are accepted when their
        center is inside the walkable area.

    Returns
    -------
    dict[str, SquareCell]
        Dictionary of accepted square cells indexed by cell_id.
    """
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
            cell_id = str(next_id)
            cells[cell_id] = SquareCell(
                cell_id=cell_id,
                polygon=square,
                center=center,
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
                cell_id = str(next_id)
                cells[cell_id] = SquareCell(
                    cell_id=cell_id,
                    polygon=square,
                    center=center,
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
) -> dict[str, tuple[list[float], float]]:
    """
    Build waypoints from the center of each square cell.

    Parameters
    ----------
    cells:
        Accepted square cells.
    radius:
        Fixed waypoint radius. If provided, it is used for every waypoint.
    radius_ratio:
        Used only when `radius` is None. The radius becomes `cell.size * radius_ratio`.

    Returns
    -------
    dict[str, tuple[list[float], float]]
        Mapping: cell_id -> ([x, y], radius)
    """
    if radius is not None and radius <= 0:
        raise ValueError("radius must be > 0")

    if radius is None and radius_ratio <= 0:
        raise ValueError("radius_ratio must be > 0")

    return {
        cell_id: (
            [cell.center[0], cell.center[1]],
            radius if radius is not None else cell.size * radius_ratio,
        )
        for cell_id, cell in cells.items()
    }


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
) -> tuple[list[list[bool]], float, float, int, int]:
    minx, miny, maxx, maxy = walkable_area.bounds

    rows = int((maxy - miny) / base_cell_size)
    cols = int((maxx - minx) / base_cell_size)

    if rows <= 0 or cols <= 0:
        raise ValueError("Invalid grid size derived from walkable_area and base_cell_size")

    mask = [[False for _ in range(cols)] for _ in range(rows)]

    for row in range(rows):
        for col in range(cols):
            x = minx + col * base_cell_size
            y = miny + row * base_cell_size
            cell = _create_square(x, y, base_cell_size)

            if require_full_cell:
                mask[row][col] = walkable_area.covers(cell)
            else:
                center = Point(x + base_cell_size / 2.0, y + base_cell_size / 2.0)
                mask[row][col] = walkable_area.covers(center)

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


def _mark_square_used(mask: list[list[bool]], top_row: int, left_col: int, side: int) -> None:
    for r in range(top_row, top_row + side):
        for c in range(left_col, left_col + side):
            mask[r][c] = False


def build_greedy_square_cells(
    walkable_area: BaseGeometry,
    base_cell_size: float,
    min_square_size: float | None = None,
    require_full_cell: bool = True,
) -> dict[str, SquareCell]:
    """
    Build square cells by:
    1. rasterizing the walkable area at `base_cell_size`
    2. repeatedly selecting the largest available square of valid cells

    This usually produces fewer nodes than a quadtree in long rectangular corridors.
    """
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
        center = _square_center(x, y, size)

        cell_id = str(next_id)
        cells[cell_id] = SquareCell(
            cell_id=cell_id,
            polygon=square,
            center=center,
            size=size,
            level=0,
        )
        next_id += 1

        _mark_square_used(mask, best_row, best_col, best_side)

    return cells

def compute_distance(
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _share_edge(
    polygon_a,
    polygon_b,
    min_shared_length: float = 1e-9,
) -> bool:
    intersection = polygon_a.boundary.intersection(polygon_b.boundary)

    if intersection.is_empty:
        return False

    if intersection.geom_type in {"LineString", "MultiLineString"}:
        return intersection.length > min_shared_length

    return False


def build_bidirectional_weighted_edges(
    cells: dict[str, SquareCell],
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

            if not _share_edge(
                cell.polygon,
                other_cell.polygon,
                min_shared_length=min_shared_length,
            ):
                continue

            weight = compute_distance(cell.center, other_cell.center)

            edges.append((cell_id, other_id, weight))
            edges.append((other_id, cell_id, weight))
            seen_undirected_pairs.add(pair)

    return edges

def _sort_cells_for_stable_ids(
    cells: dict[str, SquareCell],
) -> list[tuple[str, SquareCell]]:
    return sorted(
        cells.items(),
        key=lambda item: (
            round(item[1].center[1], 6),  # y
            round(item[1].center[0], 6),  # x
        ),
    )


def build_grid_layout(
    cells: dict[str, SquareCell],
    radius: float | None = None,
    radius_ratio: float = 0.25,
    node_defaults: dict | None = None,
    edge_attribute_name: str = "cost",
) -> BuiltGridLayout:
    if node_defaults is None:
        node_defaults = {
            "risk": 0.0,
            "blocked": False,
            "is_stairs": False,
            "floor": 0,
        }

    sorted_cells = _sort_cells_for_stable_ids(cells)

    id_map: dict[str, str] = {}
    node_order: list[str] = []
    specific_areas: dict[str, BaseGeometry] = {}
    waypoints: dict[str, tuple[list[float], float]] = {}

    for idx, (old_cell_id, cell) in enumerate(sorted_cells, start=1):
        new_id = str(idx)
        id_map[old_cell_id] = new_id
        node_order.append(new_id)

        specific_areas[new_id] = cell.polygon

        waypoint_radius = radius if radius is not None else cell.size * radius_ratio
        waypoints[new_id] = ([cell.center[0], cell.center[1]], waypoint_radius)

    raw_edges = build_bidirectional_weighted_edges(cells)

    graph = nx.DiGraph()

    for node_id in node_order:
        graph.add_node(node_id, **node_defaults)

    for source_old, target_old, weight in raw_edges:
        source_new = id_map[source_old]
        target_new = id_map[target_old]
        graph.add_edge(source_new, target_new, **{edge_attribute_name: weight})

    return BuiltGridLayout(
        waypoints=waypoints,
        specific_areas=specific_areas,
        graph=graph,
        node_order=node_order,
    )