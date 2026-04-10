from __future__ import annotations

from shapely.geometry import Polygon

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    build_greedy_square_cells,
    build_grid_layout,
)


def print_specific_areas_python(specific_areas) -> None:
    print("specific_areas = {")

    for key in sorted(specific_areas, key=lambda x: int(x)):
        polygon = specific_areas[key]

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


def main() -> None:
    env = select_environment("management_building_basement")
    walkable_geometry = env.walkable_area.polygon

    cells = build_greedy_square_cells(
        walkable_area=walkable_geometry,
        base_cell_size=1.0,
        min_square_size=None,
        require_full_cell=False,  # mejor para cubrir más área
    )

    layout = build_grid_layout(
        cells=cells,
        radius=2.0,
        edge_attribute_name="cost",
        node_defaults={
            "risk": 0.0,
            "blocked": False,
            "is_stairs": False,
            "floor": 0,
        },
        walkable_area=walkable_geometry,
    )

    print(f"Generated nodes: {len(layout.node_order)}")
    print(f"Generated waypoints: {len(layout.waypoints)}")
    print(f"Generated specific areas: {len(layout.specific_areas)}")
    print(f"Generated graph edges: {layout.graph.number_of_edges()}")

    print("\nWaypoints:")
    for node_id in layout.node_order:
        print(f'"{node_id}": {layout.waypoints[node_id]}')

    print("\nEdges:")
    print(list(layout.graph.edges(data=True)))

    print("\nSpecific areas:")
    print_specific_areas_python(layout.specific_areas)


if __name__ == "__main__":
    main()