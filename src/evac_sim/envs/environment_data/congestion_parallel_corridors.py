from __future__ import annotations

from functools import lru_cache

import networkx as nx
from shapely.geometry import Polygon

from evac_sim.envs.environment import Environment, remove_obstacles_from_areas
from evac_sim.envs.utils import add_edges_with_capacity


@lru_cache(maxsize=None)
def get_parallel_corridors():
    complete_area = Polygon([
        (0, 0),
        (60, 0),
        (60, 18),
        (0, 18),
    ])

    obstacles = [
        # Central blocks creating two parallel corridors and two vertical connectors
        Polygon([(0, 7), (18, 7), (18, 11), (0, 11)]),
        Polygon([(22, 7), (38, 7), (38, 11), (22, 11)]),
        Polygon([(42, 7), (60, 7), (60, 11), (42, 11)]),
    ]

    waypoints = {
        "1": ([3.5, 3.5], 1.75),
        "2": ([10.5, 3.5], 1.75),
        "3": ([17.5, 3.5], 1.75),
        "4": ([24.5, 3.5], 1.75),
        "5": ([31.5, 3.5], 1.75),
        "6": ([38.5, 3.5], 1.75),
        "7": ([45.5, 3.5], 1.75),
        "8": ([52.5, 3.5], 1.75),

        "9": ([3.5, 14.5], 1.75),
        "10": ([10.5, 14.5], 1.75),
        "11": ([17.5, 14.5], 1.75),
        "12": ([24.5, 14.5], 1.75),
        "13": ([31.5, 14.5], 1.75),
        "14": ([38.5, 14.5], 1.75),
        "15": ([45.5, 14.5], 1.75),
        "16": ([52.5, 14.5], 1.75),

        "17": ([58.0, 2.0], 1.0),
        "18": ([20.0, 9.0], 1.0),
        "19": ([40.0, 9.0], 1.0),
        "20": ([58.0, 13.0], 1.0),
        "21": ([58.0, 5.5], 1.0),
        "22": ([58.0, 16.5], 1.0),
    }

    G = nx.DiGraph()

    for node, _ in waypoints.items():
        G.add_node(node, risk=0.0, blocked=False, is_stairs=False, floor=0)

    edges = [
        # Lower corridor connections
        ("1", "2", 7.0, 49),
        ("2", "1", 7.0, 49),
        ("2", "3", 7.0, 49),
        ("3", "2", 7.0, 49),
        ("3", "4", 7.0, 49),
        ("4", "3", 7.0, 49),

        # First vertical connector
        ("3", "18", 6.041522986797286, 16),
        ("18", "3", 6.041522986797286, 16),

        ("4", "5", 7.0, 49),
        ("5", "4", 7.0, 49),

        # First vertical connector
        ("4", "18", 7.106335201775948, 16),
        ("18", "4", 7.106335201775948, 16),

        ("5", "6", 7.0, 49),
        ("6", "5", 7.0, 49),

        # Second vertical connector
        ("6", "19", 5.70087712549569, 16),
        ("19", "6", 5.70087712549569, 16),

        ("6", "7", 7.0, 49),
        ("7", "6", 7.0, 49),
        ("7", "8", 7.0, 49),
        ("8", "7", 7.0, 49),

        # Right exit approach from the lower corridor
        ("8", "17", 5.70087712549569, 16),
        ("17", "8", 5.70087712549569, 16),
        ("8", "21", 5.852349955359813, 12),
        ("21", "8", 5.852349955359813, 12),

        # Upper corridor connections
        ("9", "10", 7.0, 49),
        ("10", "9", 7.0, 49),
        ("10", "11", 7.0, 49),
        ("11", "10", 7.0, 49),

        # First vertical connector
        ("11", "18", 6.041522986797286, 16),
        ("18", "11", 6.041522986797286, 16),

        ("11", "12", 7.0, 49),
        ("12", "11", 7.0, 49),

        # First vertical connector
        ("12", "18", 7.106335201775948, 16),
        ("18", "12", 7.106335201775948, 16),

        ("12", "13", 7.0, 49),
        ("13", "12", 7.0, 49),
        ("13", "14", 7.0, 49),
        ("14", "13", 7.0, 49),

        # Second vertical connector
        ("14", "19", 5.70087712549569, 16),
        ("19", "14", 5.70087712549569, 16),

        ("14", "15", 7.0, 49),
        ("15", "14", 7.0, 49),
        ("15", "16", 7.0, 49),
        ("16", "15", 7.0, 49),

        # Right exit approach from the upper corridor
        ("16", "20", 5.70087712549569, 16),
        ("20", "16", 5.70087712549569, 16),
        ("16", "22", 5.852349955359813, 12),
        ("22", "16", 5.852349955359813, 12),

        # Lower right exit area
        ("17", "21", 3.5, 12),
        ("21", "17", 3.5, 12),

        # Upper right exit area
        ("20", "22", 3.5, 12),
        ("22", "20", 3.5, 12),
    ]

    add_edges_with_capacity(G, edges)

    specific_areas = {
        # Lower corridor
        "1": Polygon([(7, 0), (0, 0), (0, 7), (7, 7)]),
        "2": Polygon([(14, 0), (7, 0), (7, 7), (14, 7)]),
        "3": Polygon([(21, 7), (21, 0), (14, 0), (14, 7), (18, 7)]),
        "4": Polygon([(28, 0), (21, 0), (21, 7), (22, 7), (28, 7)]),
        "5": Polygon([(35, 0), (28, 0), (28, 7), (35, 7)]),
        "6": Polygon([(42, 0), (35, 0), (35, 7), (38, 7), (42, 7)]),
        "7": Polygon([(49, 0), (42, 0), (42, 7), (49, 7)]),
        "8": Polygon([(56, 0), (49, 0), (49, 7), (56, 7)]),

        # Upper corridor
        "9": Polygon([(7, 11), (0, 11), (0, 18), (7, 18)]),
        "10": Polygon([(14, 11), (7, 11), (7, 18), (14, 18)]),
        "11": Polygon([(21, 11), (18, 11), (14, 11), (14, 18), (21, 18)]),
        "12": Polygon([(28, 11), (22, 11), (21, 11), (21, 18), (28, 18)]),
        "13": Polygon([(35, 11), (28, 11), (28, 18), (35, 18)]),
        "14": Polygon([(42, 11), (38, 11), (35, 11), (35, 18), (42, 18)]),
        "15": Polygon([(49, 11), (42, 11), (42, 18), (49, 18)]),
        "16": Polygon([(56, 11), (49, 11), (49, 18), (56, 18)]),

        # Right-side lower exit approach
        "17": Polygon([(60, 0), (56, 0), (56, 4), (60, 4)]),

        # Vertical connectors
        "18": Polygon([(22, 7), (18, 7), (18, 11), (22, 11)]),
        "19": Polygon([(42, 7), (38, 7), (38, 11), (42, 11)]),

        # Right-side upper exit approach
        "20": Polygon([(60, 11), (56, 11), (56, 15), (60, 15)]),

        # Right-side lower exit area
        "21": Polygon([(60, 4), (56, 4), (56, 7), (60, 7)]),

        # Right-side upper exit area
        "22": Polygon([(60, 15), (56, 15), (56, 18), (60, 18)]),
    }

    return Environment(
        name="parallel_corridors",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        waypoints=waypoints,
        sources=[],
        targets=[],
        specific_areas=specific_areas,
    )