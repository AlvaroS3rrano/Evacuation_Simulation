from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
import pedpy
from matplotlib.patches import Circle
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from evac_sim.envs.environment_factory import select_environment
from evac_sim.envs.layout_creation import (
    SquareCell,
    build_adaptive_square_cells,
    build_bidirectional_weighted_edges,
    build_convex_navmesh_cells,
    build_greedy_square_cells,
    get_waypoints_from_cells,
)
from evac_sim.envs.layout_io import save_layout_json


@dataclass(frozen=True)
class LayoutGenerationConfig:
    env: str
    algorithm: str
    min_cell_size: float
    max_cell_size: float | None
    accept_partial_min_cells: bool
    greedy_min_square_size: float | None
    greedy_center_within: bool
    navmesh_min_area: float
    navmesh_max_area: float | None
    waypoint_radius: float | None
    radius_ratio: float
    min_waypoint_radius: float
    max_waypoint_radius: float | None
    output_root: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an editable layout JSON and a layout preview image from an "
            "environment walkable area."
        )
    )

    parser.add_argument("--env", required=True, help="Environment name registered in environment_factory.py")
    parser.add_argument(
        "--algorithm",
        "--method",
        dest="algorithm",
        choices=["greedy", "quadtree", "convex_navmesh"],
        required=True,
        help="Layout generation algorithm.",
    )

    parser.add_argument(
        "--output-root",
        default="../generated_layouts",
        help="Root folder where timestamped generated layouts will be stored.",
    )

    # Shared / square-grid parameters
    parser.add_argument(
        "--min-cell-size",
        type=float,
        default=1.0,
        help="Greedy base cell size or quadtree minimum cell size.",
    )
    parser.add_argument(
        "--max-cell-size",
        type=float,
        default=None,
        help="Quadtree maximum initial cell size. Ignored by greedy and convex_navmesh.",
    )

    # Quadtree
    parser.add_argument(
        "--accept-partial-min-cells",
        action="store_true",
        help="Quadtree: accept min-size cells clipped by the walkable area if their center is inside.",
    )

    # Greedy
    parser.add_argument(
        "--greedy-min-square-size",
        type=float,
        default=None,
        help="Greedy: minimum square size to keep. Defaults to --min-cell-size.",
    )
    parser.add_argument(
        "--greedy-center-within",
        action="store_true",
        help="Greedy: accept base cells by center-inside instead of full-cell coverage.",
    )

    # Navmesh
    parser.add_argument(
        "--navmesh-min-area",
        type=float,
        default=0.02,
        help="Convex navmesh: discard triangles smaller than this area.",
    )
    parser.add_argument(
        "--navmesh-max-area",
        type=float,
        default=0.35,
        help="Convex navmesh: subdivide triangles larger than this area. Use <=0 to disable.",
    )

    # Waypoints
    parser.add_argument(
        "--waypoint-radius",
        type=float,
        default=None,
        help="Fixed waypoint acceptance radius. If omitted, radius_ratio is used.",
    )
    parser.add_argument(
        "--radius-ratio",
        type=float,
        default=None,
        help=(
            "Waypoint radius as a fraction of cell size. Defaults to 0.18 for "
            "convex_navmesh and 0.25 otherwise."
        ),
    )
    parser.add_argument(
        "--min-waypoint-radius",
        type=float,
        default=0.10,
        help="Minimum waypoint acceptance radius.",
    )
    parser.add_argument(
        "--max-waypoint-radius",
        type=float,
        default=None,
        help=(
            "Maximum waypoint acceptance radius. Recommended for convex_navmesh. "
            "Defaults to 0.30 for convex_navmesh and no limit otherwise."
        ),
    )

    # Preview
    parser.add_argument("--show-cell-id", action="store_true", default=True, help="Show cell ids in preview.")
    parser.add_argument("--hide-cell-id", action="store_false", dest="show_cell_id", help="Hide cell ids.")
    parser.add_argument("--show-node-id", action="store_true", default=True, help="Show waypoint/node ids.")
    parser.add_argument("--hide-node-id", action="store_false", dest="show_node_id", help="Hide waypoint/node ids.")
    parser.add_argument("--show-edge-weights", action="store_true", help="Show edge costs in preview.")
    parser.add_argument("--dpi", type=int, default=220, help="Preview PNG resolution.")

    return parser.parse_args()


def _normalise_args(args: argparse.Namespace) -> LayoutGenerationConfig:
    radius_ratio = args.radius_ratio
    if radius_ratio is None:
        radius_ratio = 0.18 if args.algorithm == "convex_navmesh" else 0.25

    max_waypoint_radius = args.max_waypoint_radius
    if max_waypoint_radius is None and args.algorithm == "convex_navmesh":
        max_waypoint_radius = 0.30

    navmesh_max_area = args.navmesh_max_area
    if navmesh_max_area is not None and navmesh_max_area <= 0:
        navmesh_max_area = None

    return LayoutGenerationConfig(
        env=args.env,
        algorithm=args.algorithm,
        min_cell_size=args.min_cell_size,
        max_cell_size=args.max_cell_size,
        accept_partial_min_cells=args.accept_partial_min_cells,
        greedy_min_square_size=args.greedy_min_square_size,
        greedy_center_within=args.greedy_center_within,
        navmesh_min_area=args.navmesh_min_area,
        navmesh_max_area=navmesh_max_area,
        waypoint_radius=args.waypoint_radius,
        radius_ratio=radius_ratio,
        min_waypoint_radius=args.min_waypoint_radius,
        max_waypoint_radius=max_waypoint_radius,
        output_root=args.output_root,
    )


def _build_cells(config: LayoutGenerationConfig, geometry: BaseGeometry) -> dict[str, SquareCell]:
    if config.algorithm == "greedy":
        return build_greedy_square_cells(
            walkable_area=geometry,
            base_cell_size=config.min_cell_size,
            min_square_size=config.greedy_min_square_size,
            require_full_cell=not config.greedy_center_within,
        )

    if config.algorithm == "quadtree":
        return build_adaptive_square_cells(
            walkable_area=geometry,
            min_cell_size=config.min_cell_size,
            max_cell_size=config.max_cell_size,
            accept_partial_min_cells=config.accept_partial_min_cells,
        )

    if config.algorithm == "convex_navmesh":
        return build_convex_navmesh_cells(
            walkable_area=geometry,
            min_area=config.navmesh_min_area,
            max_area=config.navmesh_max_area,
        )

    raise ValueError(f"Unknown algorithm: {config.algorithm}")


def _shared_boundary_length(polygon_a: BaseGeometry, polygon_b: BaseGeometry) -> float:
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


def _build_graph(
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
) -> nx.DiGraph:
    graph = nx.DiGraph()

    for node_id in cells:
        graph.add_node(
            node_id,
            risk=0.0,
            blocked=False,
            is_stairs=False,
            floor=0,
        )

    for source, target, cost in edges:
        portal_width = _shared_boundary_length(
            cells[source].polygon,
            cells[target].polygon,
        )

        graph.add_edge(
            source,
            target,
            cost=float(cost),
            portal_width=portal_width,
            capacity=max(1, math.floor(portal_width)) if portal_width > 0 else 1,
            occupancy=0,
        )

    return graph


def _output_dir(config: LayoutGenerationConfig) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{timestamp}_{config.env}_{config.algorithm}"
    return Path(config.output_root) / folder_name


def _draw_cell(ax, cell_id: str, cell: SquareCell, *, show_cell_id: bool) -> None:
    x, y = cell.polygon.exterior.xy
    ax.plot(x, y, linewidth=0.65, color="black", alpha=0.75, zorder=2)

    if show_cell_id:
        point = cell.polygon.representative_point()
        ax.annotate(
            cell_id,
            (point.x, point.y),
            ha="center",
            va="center",
            fontsize=6,
            color="navy",
            bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.75},
            zorder=4,
        )


def _draw_edges(
    ax,
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
    *,
    show_edge_weights: bool,
) -> None:
    drawn_pairs: set[tuple[str, str]] = set()

    for source, target, cost in edges:
        pair = tuple(sorted((source, target)))
        if pair in drawn_pairs:
            continue

        p1 = cells[source].center
        p2 = cells[target].center

        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], linewidth=0.55, color="gray", alpha=0.55, zorder=1)

        if show_edge_weights:
            ax.annotate(
                f"{cost:.2f}",
                ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                ha="center",
                va="center",
                fontsize=5,
                color="darkgreen",
                bbox={"boxstyle": "round,pad=0.08", "fc": "white", "ec": "none", "alpha": 0.7},
                zorder=3,
            )

        drawn_pairs.add(pair)


def _draw_waypoints(
    ax,
    waypoints: dict[str, tuple[list[float], float]],
    *,
    show_node_id: bool,
) -> None:
    for node_id, (point, radius) in waypoints.items():
        x, y = point
        ax.plot(x, y, "o", markersize=2.8, color="red", zorder=5)
        ax.add_patch(Circle((x, y), radius, fc="red", ec="red", alpha=0.08, zorder=4))

        if show_node_id:
            ax.annotate(
                node_id,
                (x, y),
                textcoords="offset points",
                xytext=(0, 7),
                ha="center",
                va="bottom",
                fontsize=6,
                color="darkred",
                bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.75},
                zorder=6,
            )


def save_layout_preview(
    *,
    output_file: Path,
    env_name: str,
    algorithm: str,
    walkable_area,
    cells: dict[str, SquareCell],
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
    show_cell_id: bool,
    show_node_id: bool,
    show_edge_weights: bool,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(24, 16))
    ax.set_aspect("equal")

    pedpy.plot_walkable_area(walkable_area=walkable_area, axes=ax)

    for cell_id, cell in cells.items():
        _draw_cell(ax, cell_id, cell, show_cell_id=show_cell_id)

    _draw_edges(ax, cells, edges, show_edge_weights=show_edge_weights)
    _draw_waypoints(ax, waypoints, show_node_id=show_node_id)

    ax.set_title(
        f"Generated layout | env={env_name} | algorithm={algorithm} | "
        f"cells={len(cells)} | edges={len(edges)}"
    )

    fig.tight_layout()
    fig.savefig(output_file, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_metadata(path: Path, *, config: LayoutGenerationConfig, cells_count: int, edges_count: int) -> None:
    metadata = {
        "config": asdict(config),
        "summary": {
            "cells": cells_count,
            "directed_edges": edges_count,
            "undirected_edges": edges_count // 2,
        },
    }

    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = _normalise_args(args)

    env = select_environment(config.env)
    walkable_area = env.walkable_area
    geometry = walkable_area.polygon

    cells = _build_cells(config, geometry)
    edges = build_bidirectional_weighted_edges(cells, walkable_area=geometry)

    waypoints = get_waypoints_from_cells(
        cells,
        radius=config.waypoint_radius,
        radius_ratio=config.radius_ratio,
        min_radius=config.min_waypoint_radius,
        max_radius=config.max_waypoint_radius,
    )

    graph = _build_graph(cells, edges)

    output_dir = _output_dir(config)
    output_dir.mkdir(parents=True, exist_ok=True)

    layout_json = output_dir / "layout.json"
    preview_png = output_dir / "layout_preview.png"
    metadata_json = output_dir / "metadata.json"

    save_layout_json(
        layout_json,
        waypoints=waypoints,
        specific_areas={cell_id: cell.polygon for cell_id, cell in cells.items()},
        graph=graph,
        target_nodes=getattr(env, "targets", []),
        metadata={
            "environment": config.env,
            "algorithm": config.algorithm,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "config": asdict(config),
        },
    )

    save_layout_preview(
        output_file=preview_png,
        env_name=config.env,
        algorithm=config.algorithm,
        walkable_area=walkable_area,
        cells=cells,
        edges=edges,
        waypoints=waypoints,
        show_cell_id=args.show_cell_id,
        show_node_id=args.show_node_id,
        show_edge_weights=args.show_edge_weights,
        dpi=args.dpi,
    )

    save_metadata(
        metadata_json,
        config=config,
        cells_count=len(cells),
        edges_count=len(edges),
    )

    print(f"Generated layout folder: {output_dir}")
    print(f"  JSON:    {layout_json}")
    print(f"  Preview: {preview_png}")
    print(f"  Meta:    {metadata_json}")


if __name__ == "__main__":
    main()
