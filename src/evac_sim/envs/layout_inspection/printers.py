from __future__ import annotations

from shapely.geometry import Polygon


def _sort_key(value):
    return int(value) if str(value).isdigit() else str(value)


def print_waypoints_python(waypoints: dict[str, tuple[list[float], float]]) -> None:
    print("waypoints = {")
    for key in sorted(waypoints, key=_sort_key):
        point, radius = waypoints[key]
        print(f'    "{key}": ({point}, {radius}),')
    print("}")


def print_node_capacities_python(node_capacities: dict[str, int]) -> None:
    print("node_capacities = {")
    for key in sorted(node_capacities, key=_sort_key):
        print(f'    "{key}": {node_capacities[key]},')
    print("}")


def print_edges_python(edges: list[tuple[str, str, float, int]]) -> None:
    print("edges = [")
    for source, target, weight, capacity_value in edges:
        print(f'    ("{source}", "{target}", {weight}, {capacity_value}),')
    print("]")


def print_specific_areas_python(cells) -> None:
    print("specific_areas = {")

    for key in sorted(cells, key=_sort_key):
        cell_or_polygon = cells[key]
        polygon = getattr(cell_or_polygon, "polygon", cell_or_polygon)

        if not isinstance(polygon, Polygon):
            print(f'    "{key}": {polygon.wkt},')
            continue

        coords = list(polygon.exterior.coords)[:-1]

        coords_str = ", ".join(
            f"({int(x) if float(x).is_integer() else x}, "
            f"{int(y) if float(y).is_integer() else y})"
            for x, y in coords
        )

        print(f'    "{key}": Polygon([{coords_str}]),')

    print("}")