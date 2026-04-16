from __future__ import annotations

from functools import lru_cache

import networkx as nx
from shapely.geometry import Polygon

from evac_sim.envs.environment import Environment, remove_obstacles_from_areas

@lru_cache(maxsize=None)
def get_corridor_environment():
    complete_area = Polygon(
        [
            (0, 0),
            (40, 0),
            (40, -5),
            (45, -5),
            (45, 0),
            (70, 0),
            (70, 5),
            (55, 5),
            (55, 10),
            (50, 10),
            (50, 5),
            (0, 5),
        ]
    )

    obstacles = []

    waypoints = {
        "1": ([2.5, 2.5], 2.0),
        "2": ([7.5, 2.5], 2.0),
        "3": ([12.5, 2.5], 2.0),
        "4": ([17.5, 2.5], 2.0),
        "5": ([22.5, 2.5], 2.0),
        "6": ([27.5, 2.5], 2.0),
        "7": ([32.5, 2.5], 2.0),
        "8": ([37.5, 2.5], 2.0),
        "9": ([42.5, 2.5], 2.0),
        "10": ([47.5, 2.5], 2.0),
        "11": ([52.5, 2.5], 2.0),
        "12": ([57.5, 2.5], 2.0),
        "13": ([62.5, 2.0], 2.0),
        "14": ([67.5, 2.5], 2.0),
        "15": ([52.5, 7.5], 2.0),
        "16": ([42.5, -2.5], 2.0),
    }

    # Create the graph
    G = nx.DiGraph()

    nodes = {str(i): 0.0 for i in range(1, 17)}

    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    # Connections (linear corridor + branches to areas 15 and 16)
    edges = []
    for i in range(1, 14):
        edges.append((str(i), str(i + 1)))
        edges.append((str(i + 1), str(i)))

    # Connections for special areas
    edges += [
        ("11", "15"),
        ("15", "11"),
        ("9", "16"),
        ("16", "9"),
    ]

    G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])

    specific_areas = {
        "1": Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]),
        "2": Polygon([(5, 0), (10, 0), (10, 5), (5, 5)]),
        "3": Polygon([(10, 0), (15, 0), (15, 5), (10, 5)]),
        "4": Polygon([(15, 0), (20, 0), (20, 5), (15, 5)]),
        "5": Polygon([(20, 0), (25, 0), (25, 5), (20, 5)]),
        "6": Polygon([(25, 0), (30, 0), (30, 5), (25, 5)]),
        "7": Polygon([(30, 0), (35, 0), (35, 5), (30, 5)]),
        "8": Polygon([(35, 0), (40, 0), (40, 5), (35, 5)]),
        "9": Polygon([(40, 0), (45, 0), (45, 5), (40, 5)]),
        "10": Polygon([(45, 0), (50, 0), (50, 5), (45, 5)]),
        "11": Polygon([(50, 0), (55, 0), (55, 5), (50, 5)]),
        "12": Polygon([(55, 0), (60, 0), (60, 5), (55, 5)]),
        "13": Polygon([(60, 0), (65, 0), (65, 5), (60, 5)]),
        "14": Polygon([(65, 0), (70, 0), (70, 5), (65, 5)]),
        "15": Polygon([(50, 5), (55, 5), (55, 10), (50, 10)]),
        "16": Polygon([(40, -5), (45, -5), (45, 0), (40, 0)]),
    }

    return Environment(
        name="corridor",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        waypoints=waypoints,
        sources=["16"],
        targets=["1", "14"],
        specific_areas=specific_areas,
    )