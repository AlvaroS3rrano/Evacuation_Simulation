from __future__ import annotations

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    build_greedy_square_cells,
    build_grid_layout,
)


def print_specific_areas_python(specific_areas) -> None:
    print("specific_areas = {")

    for key in sorted(specific_areas, key=lambda x: int(x)):
        polygon = specific_areas[key]

        coords = list(polygon.exterior.coords)

        coords = coords[:-1]

        coords_str = ", ".join(
            f"({int(x) if x.is_integer() else x}, {int(y) if y.is_integer() else y})" for x, y in coords)

        print(f'    "{key}": Polygon([{coords_str}]),')

    print("}")


def main() -> None:
    env = select_environment("corridor")

    cells = build_greedy_square_cells(
        walkable_area=env.walkable_area.polygon,
        base_cell_size=1.0,
        min_square_size=None,
        require_full_cell=True,
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
    )

    print(f"Generated nodes: {len(layout.node_order)}")
    print(f"Generated waypoints: {len(layout.waypoints)}")
    print(f"Generated specific areas: {len(layout.specific_areas)}")
    print(f"Generated graph edges: {layout.graph.number_of_edges()}")

    for node_id in layout.node_order:
        print(f"\"{node_id}\": {layout.waypoints[node_id]}")

    print(list(layout.graph.edges(data=True)))

    print_specific_areas_python(layout.specific_areas)


if __name__ == "__main__":
    main()