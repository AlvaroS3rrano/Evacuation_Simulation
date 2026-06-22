from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import math
import networkx as nx
import pedpy
import shapely
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

@dataclass(slots=True)
class Environment:
    name: str
    graph: nx.DiGraph
    complete_area: Polygon
    obstacles: Sequence[Polygon]
    waypoints: Mapping[str, tuple[list[float], float]]
    sources: Sequence[str]
    targets: Sequence[str]
    specific_areas: Mapping[str, BaseGeometry]
    floors: Any = None
    floor_number: int = 1
    floor_connecting_nodes: Any = None

    obstacle: BaseGeometry = field(init=False)
    walkable_area: pedpy.WalkableArea = field(init=False)

    def __post_init__(self) -> None:
        if self.obstacles:
            obstacle_union = shapely.union_all(self.obstacles)
            walkable_geometry = shapely.difference(self.complete_area, obstacle_union)
        else:
            obstacle_union = shapely.GeometryCollection()
            walkable_geometry = self.complete_area

        self.obstacle = obstacle_union
        self.walkable_area = pedpy.WalkableArea(walkable_geometry)


def remove_obstacles_from_areas(
    specific_areas: Mapping[str, BaseGeometry],
    obstacles: Sequence[Polygon],
) -> dict[str, BaseGeometry]:
    if not obstacles:
        return dict(specific_areas)

    obstacle_union = shapely.union_all(obstacles)
    return {
        name: area.difference(obstacle_union) if area.intersects(obstacle_union) else area
        for name, area in specific_areas.items()
    }

def set_targets(target_ids: Sequence[str], env: Environment) -> None:
    for target_id in target_ids:
        env.waypoints.pop(target_id, None)














