from __future__ import annotations

from functools import lru_cache

import networkx as nx
from shapely.geometry import Polygon

from evac_sim.envs.environment import Environment, remove_obstacles_from_areas


@lru_cache(maxsize=None)
def get_simple_3x3():
    complete_area = Polygon(
        [
            (0, 0),
            (0, 15),
            (15, 15),
            (15, 0),
        ]
    )
    obstacles = [
        # bottom
        Polygon([(4.9, 0.0), (4.9, 1.5), (5.1, 1.5), (5.1, 0.0)]),
        Polygon([(9.9, 0.0), (9.9, 1.5), (10.1, 1.5), (10.1, 0.0)]),
        # right
        Polygon([(13.6, 4.9), (15, 4.9), (15, 5.1), (13.6, 5.1)]),
        Polygon([(13.6, 9.9), (15, 9.9), (15, 10.1), (13.6, 10.1)]),
        # top
        Polygon([(4.9, 15), (4.9, 13.6), (5.1, 13.6), (5.1, 15)]),
        Polygon([(9.9, 15), (9.9, 13.6), (10.1, 13.6), (10.1, 15)]),
        # left
        Polygon([(1.5, 4.9), (0, 4.9), (0, 5.1), (1.5, 5.1)]),
        Polygon([(1.5, 9.9), (0, 9.9), (0, 10.1), (1.5, 10.1)]),
        # center
        ## bottom left
        Polygon(
            [
                (3.6, 4.9),
                (4.9, 4.9),
                (4.9, 3.6),
                (5.1, 3.6),
                (5.1, 4.9),
                (6.4, 4.9),
                (6.4, 5.1),
                (5.1, 5.1),
                (5.1, 6.5),
                (4.9, 6.5),
                (4.9, 5.1),
                (3.6, 5.1),
            ]
        ),
        ## bottom right
        Polygon(
            [
                (8.6, 4.9),
                (9.9, 4.9),
                (9.9, 3.6),
                (10.1, 3.6),
                (10.1, 4.9),
                (11.5, 4.9),
                (11.5, 5.1),
                (10.1, 5.1),
                (10.1, 6.5),
                (9.9, 6.5),
                (9.9, 5.1),
                (8.6, 5.1),
            ]
        ),
        ## top left
        Polygon(
            [
                (3.6, 9.9),
                (4.9, 9.9),
                (4.9, 8.6),
                (5.1, 8.6),
                (5.1, 9.9),
                (6.4, 9.9),
                (6.4, 10.1),
                (5.1, 10.1),
                (5.1, 11.5),
                (4.9, 11.5),
                (4.9, 10.1),
                (3.6, 10.1),
            ]
        ),
        ## top right
        Polygon(
            [
                (8.6, 9.9),
                (9.9, 9.9),
                (9.9, 8.6),
                (10.1, 8.6),
                (10.1, 9.9),
                (11.5, 9.9),
                (11.5, 10.1),
                (10.1, 10.1),
                (10.1, 11.5),
                (9.9, 11.5),
                (9.9, 10.1),
                (8.6, 10.1),
            ]
        ),
    ]

    waypoints = {
        "A": ([2.5, 2.5], 1.5),
        "B": ([7.5, 2.5], 1.5),
        "C": ([12.5, 2.5], 1.5),
        "D": ([12.5, 7.5], 1.5),
        "E": ([7.5, 7.5], 1.5),
        "F": ([2.5, 7.5], 1.5),
        "G": ([2.5, 12.5], 1.5),
        "H": ([7.5, 12.5], 1.5),
    }

    # Create the graph
    G = nx.DiGraph()

    # Nodos y sus niveles iniciales de riesgo (0 a 1)
    nodes = {
        "A": 0.0,
        "B": 0.6,
        "C": 0.0,
        "D": 0.0,
        "E": 0.6,
        "F": 0.1,
        "G": 0.0,
        "H": 0.0,
        "I": 0.0,
    }

    # Agregar nodos al grafo
    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    # Definir las conexiones entre nodos
    edges = [
        ("A", "B"),
        ("A", "F"),
        ("B", "A"),
        ("B", "E"),
        ("B", "C"),
        ("C", "B"),
        ("C", "D"),
        ("D", "I"),
        ("D", "E"),
        ("D", "C"),
        ("E", "D"),
        ("E", "F"),
        ("E", "B"),
        ("E", "H"),
        ("F", "A"),
        ("F", "E"),
        ("F", "G"),
        ("G", "F"),
        ("G", "H"),
        ("H", "E"),
        ("H", "G"),
        ("H", "I"),
    ]

    # Agregar las aristas con un costo fijo (se puede ajustar)
    G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])

    specific_areas = dict()
    specific_areas["A"] = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
    specific_areas["B"] = Polygon([(5, 0), (10, 0), (10, 5), (5, 5)])
    specific_areas["C"] = Polygon([(10, 0), (15, 0), (15, 5), (10, 5)])
    specific_areas["D"] = Polygon([(10, 5), (15, 5), (15, 10), (10, 10)])
    specific_areas["E"] = Polygon([(5, 5), (10, 5), (10, 10), (5, 10)])
    specific_areas["F"] = Polygon([(0, 5), (5, 5), (5, 10), (0, 10)])
    specific_areas["G"] = Polygon([(0, 10), (5, 10), (5, 15), (0, 15)])
    specific_areas["H"] = Polygon([(5, 10), (10, 10), (10, 15), (5, 15)])
    specific_areas["I"] = Polygon([(10, 10), (15, 10), (15, 15), (10, 15)])

    # so that the walls are properly shown
    # specific_areas = remove_obstacles_from_areas(specific_areas, obstacles)

    return Environment(
        name="simple_3x3",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        waypoints=waypoints,
        sources=["A"],
        targets=["I"],
        specific_areas=specific_areas,
    )