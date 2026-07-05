from __future__ import annotations

import matplotlib.pyplot as plt
import pedpy
from matplotlib.patches import Circle

from .geometry import get_cell_center, get_polygon


def draw_waypoint(
    ax,
    waypoint,
    distance,
    idx,
    show_node_id: bool = True,
    node_label_color: str = "darkred",
) -> None:
    ax.plot(waypoint[0], waypoint[1], "ro")

    if show_node_id:
        ax.annotate(
            f"{idx}",
            (waypoint[0], waypoint[1]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color=node_label_color,
            bbox=dict(
                boxstyle="round,pad=0.2",
                fc="white",
                ec="none",
                alpha=0.8,
            ),
            zorder=10,
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

    ax.plot(
        x,
        y,
        linewidth=0.7,
        color="black",
        alpha=0.8,
        zorder=2,
    )

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
            color="navy",
            bbox=dict(
                boxstyle="round,pad=0.15",
                fc="white",
                ec="none",
                alpha=0.7,
            ),
            zorder=3,
        )

    if show_cell_size and cell_size is not None:
        ax.annotate(
            f"{cell_size:g}",
            (centroid.x, centroid.y),
            textcoords="offset points",
            xytext=(0, -12),
            ha="center",
            va="center",
            fontsize=7,
            color="dimgray",
            bbox=dict(
                boxstyle="round,pad=0.1",
                fc="white",
                ec="none",
                alpha=0.7,
            ),
            zorder=3,
        )


def draw_edges(
    ax,
    cells,
    edges: list[tuple[str, str, float]],
    show_edge_weights: bool = False,
) -> None:
    drawn_pairs: set[tuple[str, str]] = set()

    for source, target, weight in edges:
        pair = tuple(sorted((source, target)))

        if pair in drawn_pairs:
            continue

        p1 = get_cell_center(cells[source])
        p2 = get_cell_center(cells[target])

        ax.plot(
            [p1[0], p2[0]],
            [p1[1], p2[1]],
            linewidth=0.6,
            alpha=0.5,
            color="gray",
            zorder=1,
        )

        if show_edge_weights:
            mx = (p1[0] + p2[0]) / 2
            my = (p1[1] + p2[1]) / 2

            ax.annotate(
                f"{weight:.2f}",
                (mx, my),
                textcoords="offset points",
                xytext=(0, 0),
                ha="center",
                va="center",
                fontsize=6,
                color="darkgreen",
                bbox=dict(
                    boxstyle="round,pad=0.1",
                    fc="white",
                    ec="none",
                    alpha=0.7,
                ),
                zorder=2,
            )

        drawn_pairs.add(pair)


def build_plot_title(
    args,
    cells,
    waypoints: dict[str, tuple[list[float], float]],
    edges: list[tuple[str, str, float]],
) -> str:
    if args.layout_source == "current":
        return (
            f"Current layout inspection - env={args.env}, "
            f"areas={len(cells)}, nodes={len(waypoints)}, edges={len(edges)}"
        )

    return (
        f"Grid layout / graph inspection - env={args.env}, "
        f"method={args.method}, min_cell_size={args.min_cell_size}, "
        f"cells={len(cells)}, nodes={len(waypoints)}, edges={len(edges)}"
    )


def plot_layout(
    walkable_area,
    cells,
    edges: list[tuple[str, str, float]],
    waypoints: dict[str, tuple[list[float], float]],
    args,
    output_file: str | None = None,
) -> None:
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(24, 16))
    ax.set_aspect("equal")

    pedpy.plot_walkable_area(
        walkable_area=walkable_area,
        axes=ax,
    )

    for cell_id, cell in cells.items():
        polygon = get_polygon(cell)
        cell_size = getattr(cell, "size", None)

        draw_cell(
            ax=ax,
            polygon=polygon,
            cell_id=cell_id,
            show_cell_id=args.show_cell_id,
            show_cell_size=args.show_cell_size,
            cell_size=cell_size,
        )

    draw_edges(
        ax=ax,
        cells=cells,
        edges=edges,
        show_edge_weights=args.show_edge_weights,
    )

    for node_id, (point, distance) in waypoints.items():
        draw_waypoint(
            ax=ax,
            waypoint=point,
            distance=distance,
            idx=node_id,
            show_node_id=args.show_node_id,
        )

    ax.set_title(
        build_plot_title(
            args=args,
            cells=cells,
            waypoints=waypoints,
            edges=edges,
        )
    )

    plt.tight_layout()

    if output_file is not None:
        from pathlib import Path
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_file, bbox_inches="tight", dpi=150)

    if not getattr(args, "no_plot", False):
        plt.show()
    else:
        plt.close(fig)