from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from shapely.geometry import Polygon


def polygon_to_coords(polygon: Polygon) -> list[list[float]]:
    return [[float(x), float(y)] for x, y in polygon.exterior.coords[:-1]]


def coords_to_polygon(coords: list[list[float]]) -> Polygon:
    return Polygon(coords)


def save_layout_json(
    path: str | Path,
    *,
    waypoints,
    specific_areas,
    graph,
    target_nodes=None,
    metadata: dict[str, Any] | None = None,
) -> None:
    path = Path(path)

    data = {
        "metadata": metadata or {},
        "waypoints": waypoints,
        "specific_areas": {
            node_id: polygon_to_coords(polygon)
            for node_id, polygon in specific_areas.items()
        },
        "nodes": {
            node_id: dict(graph.nodes[node_id])
            for node_id in graph.nodes
        },
        "edges": [
            {
                "source": source,
                "target": target,
                **dict(edge_data),
            }
            for source, target, edge_data in graph.edges(data=True)
        ],
        "target_nodes": target_nodes or [],
    }

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def load_layout_json(path: str | Path):
    path = Path(path)

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    graph = nx.DiGraph()

    for node_id, node_data in data["nodes"].items():
        graph.add_node(node_id, **node_data)

    for edge in data["edges"]:
        edge = dict(edge)
        source = edge.pop("source")
        target = edge.pop("target")
        graph.add_edge(source, target, **edge)

    specific_areas = {
        node_id: coords_to_polygon(coords)
        for node_id, coords in data["specific_areas"].items()
    }

    return {
        "metadata": data.get("metadata", {}),
        "waypoints": data["waypoints"],
        "specific_areas": specific_areas,
        "graph": graph,
        "target_nodes": data.get("target_nodes", []),
    }
