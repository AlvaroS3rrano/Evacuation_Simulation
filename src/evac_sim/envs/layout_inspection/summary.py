from __future__ import annotations

from collections import Counter


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


def print_layout_summary(args, cells, edges, waypoints) -> None:
    print(f"Environment: {args.env}")
    print(f"Strategy: {args.method}")
    print(f"Layout source: {args.layout_source}")
    print(f"Waypoint radius mode: {args.waypoint_radius_mode}")

    if args.layout_source == "current":
        print(f"Refresh current edges: {args.refresh_current_edges}")
        print(
            "Refresh current node capacities: "
            f"{args.refresh_current_node_capacities}"
        )
        print(f"Node density agents/m²: {args.node_density_agents_per_m2}")
        print(f"Edge flow agents/meter: {args.edge_flow_agents_per_meter}")
        print(f"Fallback edge width: {args.fallback_edge_width}")

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