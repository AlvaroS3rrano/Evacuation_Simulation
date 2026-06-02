from __future__ import annotations

from shapely.geometry import Polygon


def get_polygon(cell_or_polygon) -> Polygon:
    polygon = getattr(cell_or_polygon, "polygon", cell_or_polygon)

    if not isinstance(polygon, Polygon):
        raise TypeError(
            f"Expected Polygon-compatible cell, got {type(polygon).__name__}"
        )

    return polygon


def get_cell_center(cell_or_polygon) -> tuple[float, float]:
    if hasattr(cell_or_polygon, "center"):
        return cell_or_polygon.center

    polygon = get_polygon(cell_or_polygon)
    centroid = polygon.centroid

    return float(centroid.x), float(centroid.y)


def shared_boundary_width(source_polygon: Polygon, target_polygon: Polygon) -> float:
    boundary_intersection = source_polygon.boundary.intersection(
        target_polygon.boundary
    )

    if boundary_intersection.is_empty:
        return 0.0

    return float(boundary_intersection.length)