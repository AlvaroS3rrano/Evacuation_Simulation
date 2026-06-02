from __future__ import annotations

import argparse

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    build_bidirectional_weighted_edges,
    get_waypoints_from_cells,
)
from evac_sim.envs.layout_inspection.capacities import (
    compute_node_capacities,
    enrich_edges_with_capacity,
    enrich_edges_with_flow_capacity,
)
from evac_sim.envs.layout_inspection.current_layout import (
    build_cells_from_args,
    get_largest_waypoints_from_cells,
    load_layout_from_environment_data,
)
from evac_sim.envs.layout_inspection.plotting import plot_layout
from evac_sim.envs.layout_inspection.printers import (
    print_edges_python,
    print_node_capacities_python,
    print_specific_areas_python,
    print_waypoints_python,
)
from evac_sim.envs.layout_inspection.refresh import refresh_current_edges
from evac_sim.envs.layout_inspection.summary import print_layout_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect grid layout: walkable area, specific areas, "
            "waypoints/nodes, capacities and edges"
        )
    )

    parser.add_argument(
        "--env",
        default="corridor",
        help="Environment name",
    )

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
        help="Source of the layout: computed or current",
    )

    parser.add_argument(
        "--refresh-current-edges",
        action="store_true",
        help=(
            "Only with --layout-source current: recalculate current edge "
            "distances and print edges enriched with flow_capacity"
        ),
    )

    parser.add_argument(
        "--refresh-current-node-capacities",
        action="store_true",
        help=(
            "Only with --layout-source current: compute node_capacities from "
            "current specific_areas. This does not modify waypoints."
        ),
    )

    parser.add_argument(
        "--print-node-capacities",
        action="store_true",
        help="Print node_capacities as Python dictionary",
    )

    parser.add_argument(
        "--node-density-agents-per-m2",
        type=float,
        default=2.0,
        help=(
            "Density used to compute node_capacity from area. "
            "node_capacity = floor(area * density). Default: 2.0"
        ),
    )

    parser.add_argument(
        "--edge-flow-agents-per-meter",
        type=float,
        default=4.0,
        help=(
            "Flow used to compute flow_capacity from connection width. "
            "flow_capacity = floor(width * value). Default: 4.0"
        ),
    )

    parser.add_argument(
        "--fallback-edge-width",
        type=float,
        default=1.0,
        help=(
            "Fallback width used for flow_capacity when two connected areas "
            "do not share a measurable boundary. Default: 1.0"
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
            "the maximum radius accepted by its specific area; 'ratio' keeps "
            "the previous cell-size ratio behavior"
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
        "--max-waypoint-radius",
        type=float,
        default=0.35,
        help="Maximum waypoint acceptance radius",
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

    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> None:
    if args.refresh_current_edges and args.layout_source != "current":
        raise ValueError(
            "--refresh-current-edges can only be used with --layout-source current"
        )

    if args.refresh_current_node_capacities and args.layout_source != "current":
        raise ValueError(
            "--refresh-current-node-capacities can only be used with "
            "--layout-source current"
        )

    if args.node_density_agents_per_m2 <= 0:
        raise ValueError("--node-density-agents-per-m2 must be > 0")

    if args.edge_flow_agents_per_meter <= 0:
        raise ValueError("--edge-flow-agents-per-meter must be > 0")

    if args.fallback_edge_width <= 0:
        raise ValueError("--fallback-edge-width must be > 0")


def _load_or_build_layout(args: argparse.Namespace, env, geometry):
    if args.layout_source == "computed":
        cells = build_cells_from_args(args, geometry)
        edges = build_bidirectional_weighted_edges(
            cells,
            walkable_area=geometry,
        )

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

        return waypoints, edges, cells

    waypoints, edges, cells = load_layout_from_environment_data(env)

    if args.refresh_current_edges:
        edges = refresh_current_edges(
            edges=edges,
            waypoints=waypoints,
            walkable_geometry=geometry,
        )

    return waypoints, edges, cells


def _should_print_summary(args: argparse.Namespace) -> bool:
    return args.print_summary or (
        not args.print_waypoints
        and not args.print_edges
        and not args.print_specific_areas
        and not args.print_node_capacities
    )


def _print_requested_outputs(
    args: argparse.Namespace,
    *,
    cells,
    edges,
    waypoints,
) -> None:
    if _should_print_summary(args):
        print_layout_summary(args, cells, edges, waypoints)

    if args.print_waypoints:
        print_waypoints_python(waypoints)

    if args.print_node_capacities:
        node_capacities = compute_node_capacities(
            cells=cells,
            density_agents_per_m2=args.node_density_agents_per_m2,
        )
        print_node_capacities_python(node_capacities)

    if args.print_edges:
        if args.layout_source == "current" and args.refresh_current_edges:
            edges_to_print = enrich_edges_with_flow_capacity(
                cells=cells,
                edges=edges,
                flow_agents_per_meter=args.edge_flow_agents_per_meter,
                fallback_edge_width=args.fallback_edge_width,
            )
        else:
            edges_to_print = enrich_edges_with_capacity(
                cells=cells,
                edges=edges,
            )

        print_edges_python(edges_to_print)

    if args.print_specific_areas:
        print_specific_areas_python(cells)


def main() -> None:
    args = parse_args()
    _validate_args(args)

    env = select_environment(args.env)
    walkable_area = env.walkable_area
    geometry = walkable_area.polygon

    waypoints, edges, cells = _load_or_build_layout(
        args=args,
        env=env,
        geometry=geometry,
    )

    _print_requested_outputs(
        args,
        cells=cells,
        edges=edges,
        waypoints=waypoints,
    )

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