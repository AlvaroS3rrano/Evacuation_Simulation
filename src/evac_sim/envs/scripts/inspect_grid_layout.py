from __future__ import annotations

import argparse
from collections import Counter

import matplotlib.pyplot as plt
import pedpy
from matplotlib.patches import Circle

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    SquareCell,
    build_adaptive_square_cells,
    build_greedy_square_cells,
    get_waypoints_from_cells,
    build_bidirectional_weighted_edges,
)


def draw_waypoint(ax, waypoint, distance, idx, show_index: bool = True) -> None:
    ax.plot(waypoint[0], waypoint[1], "ro")
    if show_index:
        ax.annotate(
            f"{idx}",
            (waypoint[0], waypoint[1]),
            textcoords="offset points",
            xytext=(5, -5),
            ha="center",
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
    ax.plot(x, y, linewidth=0.6)

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
        )

    if show_cell_size and cell_size is not None:
        ax.annotate(
            f"{cell_size:g}",
            (centroid.x, centroid.y),
            textcoords="offset points",
            xytext=(0, -10),
            ha="center",
            va="center",
            fontsize=7,
        )

def draw_edges(ax, cells: dict[str, SquareCell], edges: list[tuple[str, str, float]]) -> None:
    drawn_pairs: set[tuple[str, str]] = set()

    for source, target, _ in edges:
        pair = tuple(sorted((source, target)))
        if pair in drawn_pairs:
            continue

        p1 = cells[source].center
        p2 = cells[target].center

        ax.plot(
            [p1[0], p2[0]],
            [p1[1], p2[1]],
            linewidth=0.5,
            alpha=0.5,
        )
        drawn_pairs.add(pair)

def print_cell_statistics(cells) -> None:
    size_counter = Counter()
    level_counter = Counter()

    for cell in cells.values():
        size_counter[cell.size] += 1
        level_counter[cell.level] += 1

    print("Cell statistics by size:")
    for size in sorted(size_counter):
        print(f"  size={size}: {size_counter[size]}")

    print("Cell statistics by level:")
    for level in sorted(level_counter):
        print(f"  level={level}: {level_counter[level]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect square cell decomposition over an environment"
    )
    parser.add_argument("--env", default="corridor", help="Environment name")

    parser.add_argument(
        "--method",
        type=str,
        default="greedy",
        choices=["greedy", "quadtree"],
        help="Cell generation strategy",
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
        "--show-waypoint-index",
        action="store_true",
        help="Show waypoint ids next to waypoint centers",
    )

    parser.add_argument(
        "--show-cell-id",
        action="store_true",
        help="Show cell ids at the center of each cell",
    )

    parser.add_argument(
        "--show-cell-size",
        action="store_true",
        help="Show the side length of each cell",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    env = select_environment(args.env)
    walkable_area = env.walkable_area
    geometry = walkable_area.polygon

    if args.method == "greedy":
        cells = build_greedy_square_cells(
            walkable_area=geometry,
            base_cell_size=args.min_cell_size,
            min_square_size=args.greedy_min_square_size,
            require_full_cell=not args.greedy_center_within,
        )
    else:
        cells = build_adaptive_square_cells(
            walkable_area=geometry,
            min_cell_size=args.min_cell_size,
            max_cell_size=args.max_cell_size,
            accept_partial_min_cells=args.accept_partial_min_cells,
        )

    edges = build_bidirectional_weighted_edges(cells, walkable_area=geometry)
    print(f"Directed weighted edges generated: {len(edges)}")
    print(f"Undirected connections generated: {len(edges) // 2}")

    waypoints = get_waypoints_from_cells(
        cells,
        radius=args.radius,
        radius_ratio=args.radius_ratio,
    )

    print(f"Environment: {args.env}")
    print(f"Strategy: {args.method}")
    print(f"Minimum cell size: {args.min_cell_size}")

    if args.method == "greedy":
        print(f"Greedy minimum square size: {args.greedy_min_square_size}")
        print(f"Greedy require full cell: {not args.greedy_center_within}")
    else:
        print(f"Maximum cell size: {args.max_cell_size}")
        print(f"Accept partial min cells: {args.accept_partial_min_cells}")

    print(f"Cells generated: {len(cells)}")
    print(f"Waypoints generated: {len(waypoints)}")
    print_cell_statistics(cells)

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(24, 16))
    ax.set_aspect("equal")

    pedpy.plot_walkable_area(walkable_area=walkable_area, axes=ax)

    for cell_id, cell in cells.items():
        draw_cell(
            ax=ax,
            polygon=cell.polygon,
            cell_id=cell_id,
            show_cell_id=args.show_cell_id,
            show_cell_size=args.show_cell_size,
            cell_size=cell.size,
        )

    draw_edges(ax, cells, edges)

    for waypoint_id, (point, distance) in waypoints.items():
        draw_waypoint(
            ax=ax,
            waypoint=point,
            distance=distance,
            idx=waypoint_id,
            show_index=args.show_waypoint_index,
        )

    ax.set_title(
        f"Square decomposition - env={args.env}, method={args.method}, "
        f"min_cell_size={args.min_cell_size}, cells={len(cells)}"
    )
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()