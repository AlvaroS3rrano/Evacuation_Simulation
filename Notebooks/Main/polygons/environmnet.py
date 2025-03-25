from shapely.geometry import Polygon
import networkx as nx
from .floor import Floor

class Environment:
    """
    Represents the overall environment (e.g., a building) that contains multiple floors and an associated graph.

    Attributes:
        floors: Dictionary of Floor objects, keyed by their unique identifier
        graph: Graph (e.g., using networkx) that can connect the floors.
    """

    def __init__(self, name, floors, graph):
        self.name = name
        self.floors = floors  # List of Floor objects
        self.graph = graph

def create_global_graph(floors):
    global_graph = nx.DiGraph()
    mapping = {}  # Guarda el mapeo: piso -> lista de nuevos nodos
    for floor in floors.values():
        # # Rename nodes by adding the floor name as a prefix (acting as an offset)
        # relabeled = nx.relabel_nodes(floor.graph, lambda n: f"{floor.name}_{n}")
        # # Combine graphs using disjoint_union to avoid identifier conflicts
        # global_graph = nx.disjoint_union(global_graph, relabeled)
        # mapping[floor.name] = list(relabeled.nodes)
        global_graph = nx.compose(global_graph, floor.graph)
        mapping[floor.name] = list(floor.graph.nodes)
    return global_graph

def get_floor_segment(path, env):
    """
    Given a path from the global graph, returns the contiguous segment of the path
    that belongs to the floor of the starting node.

    Parameters:
        path (list): A list of node names representing the path in the global graph.
        env (Environment): An Environment object that has a 'floors' attribute, a dictionary
                           where each value is a Floor object containing its own graph.

    Returns:
        list: The sublist of the path that belongs to the same floor as the starting node.

    Raises:
        ValueError: If the starting node is not found in any floor.
    """
    if not path:
        return []

    first_node = path[0]
    starting_floor = None

    # Find the floor that contains the starting node.
    for floor in env.floors.values():
        if first_node in floor.graph:
            starting_floor = floor
            break

    if starting_floor is None:
        raise ValueError("The starting node was not found in any floor graph.")

    # Build the segment containing nodes only from the starting floor.
    segment = []
    for node in path:
        if node in starting_floor.graph:
            segment.append(node)
        else:
            break

    return segment

def remove_obstacles_from_areas(specific_areas, obstacles):
    """
    Removes obstacles from specific areas by subtracting overlapping polygons.

    Args:
        specific_areas (dict): Dictionary of named areas {name: Polygon}.
        obstacles (list): List of Polygon objects representing obstacles.

    Returns:
        dict: Dictionary of cleaned areas {name: Polygon without obstacles}.
    """
    cleaned_areas = {}

    for name, area in specific_areas.items():
        # Subtract all obstacles from the current area
        cleaned_area = area
        for obstacle in obstacles:
            if cleaned_area.intersects(obstacle):  # Only process if they overlap
                cleaned_area = cleaned_area.difference(obstacle)
        cleaned_areas[name] = cleaned_area

    return cleaned_areas

def get_comparing_algorithms_pol():
    # Parameters for path calculation
    sources = ["C", "F"]  # Starting node for pathfinding
    targets = ["EA", "EB", "EC", "ED"]  # Target nodes for pathfinding

    complete_area = Polygon([(0, -1), (0, 17), (32, 17), (32, -1)])

    obstacles = [
        Polygon([(0, -1), (14, -1), (14, 1), (0, 1)]),
        Polygon([(16, -1), (32, -1), (32, 1), (16, 1)]),
        Polygon([(0, 15), (14, 15), (14, 17), (0, 17)]),
        Polygon([(16, 15), (32, 15), (32, 17), (16, 17)]),
        Polygon([(2, 3), (14, 3), (14, 7), (2, 7)]),
        Polygon([(16, 3), (28, 3), (28, 7), (16, 7)]),
        Polygon([(2, 9), (14, 9), (14, 13), (2, 13)]),
        Polygon([(16, 9), (28, 9), (28, 13), (16, 13)]),
        Polygon([(30, 1), (32, 1), (32, 3), (30, 3)]),
        Polygon([(30, 5), (32, 5), (32, 11), (30, 11)]),
        Polygon([(30, 13), (32, 13), (32, 17), (30, 17)]),
    ]

    exit_polygons = {
        'EA': [(14, 1), (14, -1), (16, -1), (16, 1)],
        'EB': [(14, 15), (14, 17), (16, 17), (16, 15)],
        'EC': [(30, 3), (32, 3), (32, 5), (30, 5)],
        'ED': [(30, 11), (32, 11), (32, 13), (30, 13)]
    }

    waypoints = {
        # left (8)
        'A': ([1, 14], 0.75),
        'B': ([1, 12], 0.75),
        'C': ([1, 10], 0.75),
        'D': ([1, 8], 0.75),
        'F': ([1, 6], 0.75),
        'G': ([1, 4], 0.75),
        'H': ([1, 2], 0.75),
        # bottom (13)
        'I': ([3, 2], 0.75),
        'J': ([5, 2], 0.75),
        'K': ([7, 2], 0.75),
        'L': ([9, 2], 0.75),
        'M': ([11, 2], 0.75),
        'N': ([13, 2], 0.75),
        'O': ([15, 2], 0.75),
        'P': ([17, 2], 0.75),
        'Q': ([19, 2], 0.75),
        'R': ([21, 2], 0.75),
        'S': ([23, 2], 0.75),
        'T': ([25, 2], 0.75),
        'U': ([27, 2], 0.75),
        # right (8)
        'V': ([29, 14], 0.75),
        'W': ([29, 12], 0.75),
        'X': ([29, 10], 0.75),
        'Y': ([29, 8], 0.75),
        '2A': ([29, 6], 0.75),
        '2B': ([29, 4], 0.75),
        '2C': ([29, 2], 0.75),
        # top (13)
        '2D': ([3, 14], 0.75),
        '2E': ([5, 14], 0.75),
        '2F': ([7, 14], 0.75),
        '2G': ([9, 14], 0.75),
        '2H': ([11, 14], 0.75),
        '2I': ([13, 14], 0.75),
        '2J': ([15, 14], 0.75),
        '2K': ([17, 14], 0.75),
        '2L': ([19, 14], 0.75),
        '2M': ([21, 14], 0.75),
        '2N': ([23, 14], 0.75),
        '2O': ([25, 14], 0.75),
        '2P': ([27, 14], 0.75),
        # center horizontal (11)
        '2Q': ([3, 8], 0.75),
        '2R': ([5, 8], 0.75),
        '2S': ([7, 8], 0.75),
        '2T': ([9, 8], 0.75),
        '2U': ([11, 8], 0.75),
        '2V': ([13, 8], 0.75),
        '2W': ([17, 8], 0.75),
        '2X': ([19, 8], 0.75),
        '2Y': ([21, 8], 0.75),
        '2Z': ([23, 8], 0.75),
        '3A': ([25, 8], 0.75),
        '3B': ([27, 8], 0.75),
        # center vertical (6)
        '3C': ([15, 12], 0.75),
        '3D': ([15, 10], 0.75),
        '3E': ([15, 8], 0.75),
        '3G': ([15, 6], 0.75),
        '3H': ([15, 4], 0.75)
    }

    distribution_polygons = {
        'C': Polygon([(0, 9), (2, 9), (2, 11), (0, 11)]),
        'F': Polygon([(0, 5), (2, 5), (2, 7), (0, 7)]),
    }

    G = nx.DiGraph()

    # Define nodes with their initial risk levels (0 to 1) and associated costs
    # Format: "Node": risk_level
    nodes = {
        # left (8)
        'A': 0.0,
        'B': 0.0,
        'C': 0.0,
        'D': 0.0,
        'F': 0.0,
        'G': 0.0,
        'H': 0.0,
        # bottom (13)
        'I': 0.0,
        'J': 0.0,
        'K': 0.0,
        'L': 0.0,
        'M': 0.0,
        'N': 0.0,
        'O': 0.6,
        'P': 0.0,
        'Q': 0.0,
        'R': 0.0,
        'S': 0.0,
        'T': 0.0,
        'U': 0.0,
        # right (8)
        'V': 0.0,
        'W': 0.0,
        'X': 0.0,
        'Y': 0.0,
        '2A': 0.0,
        '2B': 0.0,
        '2C': 0.0,
        # top (13)
        '2D': 0.0,
        '2E': 0.0,
        '2F': 0.0,
        '2G': 0.0,
        '2H': 0.0,
        '2I': 0.0,
        '2J': 0.0,
        '2K': 0.0,
        '2L': 0.0,
        '2M': 0.0,
        '2N': 0.0,
        '2O': 0.0,
        '2P': 0.0,
        # center horizontal (12)
        '2Q': 0.0,
        '2R': 0.0,
        '2S': 0.0,
        '2T': 0.0,
        '2U': 0.0,
        '2V': 0.0,
        '2W': 0.0,
        '2X': 0.0,
        '2Y': 0.0,
        '2Z': 0.0,
        '3A': 0.0,
        '3B': 0.0,
        # center vertical (6)
        '3C': 0.0,
        '3D': 0.0,
        '3E': 0.0,
        '3G': 0.0,
        '3H': 0.0,
        # exit polygons (4)
        'EA': 0.0,
        'EB': 0.0,
        'EC': 0.0,
        'ED': 0.0
    }

    # Add nodes to the graph with their attributes
    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    G.nodes["2R"]["is_stairs"] = True
    G.nodes["2S"]["is_stairs"] = True
    G.nodes["2Q"]["is_stairs"] = True

    # Define edges between nodes (directed connections)
    # Each tuple represents an edge: (from_node, to_node)
    edges = [

        # 1) OUTER PERIMETER
        # -- Left Side (A→H)
        ("A", "B"), ("B", "A"),
        ("B", "C"), ("C", "B"),
        ("C", "D"), ("D", "C"),
        ("D", "F"), ("F", "D"),
        ("F", "G"), ("G", "F"),
        ("G", "H"), ("H", "G"),

        # -- Bottom Side (H→U)
        ("H", "I"), ("I", "H"),
        ("I", "J"), ("J", "I"),
        ("J", "K"), ("K", "J"),
        ("K", "L"), ("L", "K"),
        ("L", "M"), ("M", "L"),
        ("M", "N"), ("N", "M"),
        ("N", "O"), ("O", "N"),
        ("O", "P"), ("P", "O"),
        ("P", "Q"), ("Q", "P"),
        ("Q", "R"), ("R", "Q"),
        ("R", "S"), ("S", "R"),
        ("S", "T"), ("T", "S"),
        ("T", "U"), ("U", "T"),

        # -- Right Side (U→V)
        ("U", "2C"), ("2C", "U"),
        ("2C", "2B"), ("2B", "2C"),
        ("2B", "2A"), ("2A", "2B"),
        ("Y", "2A"), ("Y", "2A"),
        ("Y", "X"), ("X", "Y"),
        ("X", "W"), ("W", "X"),
        ("W", "V"), ("V", "W"),

        # -- Top Side (V→A passing through 2D...2P)
        ("V", "2P"), ("2P", "V"),
        ("2P", "2O"), ("2O", "2P"),
        ("2O", "2N"), ("2N", "2O"),
        ("2N", "2M"), ("2M", "2N"),
        ("2M", "2L"), ("2L", "2M"),
        ("2L", "2K"), ("2K", "2L"),
        ("2K", "2J"), ("2J", "2K"),
        ("2J", "2I"), ("2I", "2J"),
        ("2I", "2H"), ("2H", "2I"),
        ("2H", "2G"), ("2G", "2H"),
        ("2G", "2F"), ("2F", "2G"),
        ("2F", "2E"), ("2E", "2F"),
        ("2E", "2D"), ("2D", "2E"),
        ("2D", "A"), ("A", "2D"),

        # 2) CENTRAL HORIZONTAL LINE (2Q→3B)
        ("2Q", "2R"), ("2R", "2Q"),
        ("2R", "2S"), ("2S", "2R"),
        ("2S", "2T"), ("2T", "2S"),
        ("2T", "2U"), ("2U", "2T"),
        ("2U", "2V"), ("2V", "2U"),
        ("2W", "2X"), ("2X", "2W"),
        ("2X", "2Y"), ("2Y", "2X"),
        ("2Y", "2Z"), ("2Z", "2Y"),
        ("2Z", "3A"), ("3A", "2Z"),
        ("3A", "3B"), ("3B", "3A"),

        # 3) CENTRAL VERTICAL LINE (3C→3H)
        ("3C", "3D"), ("3D", "3C"),
        ("3D", "3E"), ("3E", "3D"),
        ("3E", "3G"), ("3G", "3E"),
        ("3G", "3H"), ("3H", "3G"),

        # 4) CONNECTIONS FROM THE CENTRAL LINES TO THE PERIMETER
        ("2Q", "D"), ("D", "2Q"),

        ("2V", "3E"), ("3E", "2V"),

        ("2W", "3E"), ("3E", "2W"),

        ("3B", "Y"), ("Y", "3B"),

        # -- Connections from the central vertical line to the perimeter
        ("3C", "2J"), ("2J", "3C"),
        ("3H", "O"), ("O", "3H"),

        # 5) CONNECTIONS WITH EXITS (based on geometric proximity)
        ("EA", "O"), ("O", "EA"),
        ("EB", "2J"), ("2J", "EB"),
        ("EC", "2B"), ("2B", "EC"),
        ("ED", "W"), ("W", "ED")

    ]

    # Add the edges to the graph with cost 2 as all the areas are at the same distance
    G.add_edges_from([(u, v, {"cost": 2}) for u, v in edges])

    specific_areas = {
        # Left side (A–H)
        'A': Polygon([(0, 13), (2, 13), (2, 15), (0, 15)]),
        'B': Polygon([(0, 11), (2, 11), (2, 13), (0, 13)]),
        'C': Polygon([(0, 9), (2, 9), (2, 11), (0, 11)]),
        'D': Polygon([(0, 7), (2, 7), (2, 9), (0, 9)]),
        'F': Polygon([(0, 5), (2, 5), (2, 7), (0, 7)]),
        'G': Polygon([(0, 3), (2, 3), (2, 5), (0, 5)]),
        'H': Polygon([(0, 1), (2, 1), (2, 3), (0, 3)]),

        # Bottom side (I–U)
        'I': Polygon([(2, 1), (4, 1), (4, 3), (2, 3)]),
        'J': Polygon([(4, 1), (6, 1), (6, 3), (4, 3)]),
        'K': Polygon([(6, 1), (8, 1), (8, 3), (6, 3)]),
        'L': Polygon([(8, 1), (10, 1), (10, 3), (8, 3)]),
        'M': Polygon([(10, 1), (12, 1), (12, 3), (10, 3)]),
        'N': Polygon([(12, 1), (14, 1), (14, 3), (12, 3)]),
        'O': Polygon([(14, 1), (16, 1), (16, 3), (14, 3)]),
        'P': Polygon([(16, 1), (18, 1), (18, 3), (16, 3)]),
        'Q': Polygon([(18, 1), (20, 1), (20, 3), (18, 3)]),
        'R': Polygon([(20, 1), (22, 1), (22, 3), (20, 3)]),
        'S': Polygon([(22, 1), (24, 1), (24, 3), (22, 3)]),
        'T': Polygon([(24, 1), (26, 1), (26, 3), (24, 3)]),
        'U': Polygon([(26, 1), (28, 1), (28, 3), (26, 3)]),

        # Right side (V–2C)
        'V': Polygon([(28, 13), (30, 13), (30, 15), (28, 15)]),
        'W': Polygon([(28, 11), (30, 11), (30, 13), (28, 13)]),
        'X': Polygon([(28, 9), (30, 9), (30, 11), (28, 11)]),
        'Y': Polygon([(28, 7), (30, 7), (30, 9), (28, 9)]),
        '2A': Polygon([(28, 5), (30, 5), (30, 7), (28, 7)]),
        '2B': Polygon([(28, 3), (30, 3), (30, 5), (28, 5)]),
        '2C': Polygon([(28, 1), (30, 1), (30, 3), (28, 3)]),

        # Top side (2D–2P)
        '2D': Polygon([(2, 13), (4, 13), (4, 15), (2, 15)]),
        '2E': Polygon([(4, 13), (6, 13), (6, 15), (4, 15)]),
        '2F': Polygon([(6, 13), (8, 13), (8, 15), (6, 15)]),
        '2G': Polygon([(8, 13), (10, 13), (10, 15), (8, 15)]),
        '2H': Polygon([(10, 13), (12, 13), (12, 15), (10, 15)]),
        '2I': Polygon([(12, 13), (14, 13), (14, 15), (12, 15)]),
        '2J': Polygon([(14, 13), (16, 13), (16, 15), (14, 15)]),
        '2K': Polygon([(16, 13), (18, 13), (18, 15), (16, 15)]),
        '2L': Polygon([(18, 13), (20, 13), (20, 15), (18, 15)]),
        '2M': Polygon([(20, 13), (22, 13), (22, 15), (20, 15)]),
        '2N': Polygon([(22, 13), (24, 13), (24, 15), (22, 15)]),
        '2O': Polygon([(24, 13), (26, 13), (26, 15), (24, 15)]),
        '2P': Polygon([(26, 13), (28, 13), (28, 15), (26, 15)]),

        # Central horizontal line (2Q–3B)
        '2Q': Polygon([(2, 7), (4, 7), (4, 9), (2, 9)]),
        '2R': Polygon([(4, 7), (6, 7), (6, 9), (4, 9)]),
        '2S': Polygon([(6, 7), (8, 7), (8, 9), (6, 9)]),
        '2T': Polygon([(8, 7), (10, 7), (10, 9), (8, 9)]),
        '2U': Polygon([(10, 7), (12, 7), (12, 9), (10, 9)]),
        '2V': Polygon([(12, 7), (14, 7), (14, 9), (12, 9)]),
        '2W': Polygon([(16, 7), (18, 7), (18, 9), (16, 9)]),
        '2X': Polygon([(18, 7), (20, 7), (20, 9), (18, 9)]),
        '2Y': Polygon([(20, 7), (22, 7), (22, 9), (20, 9)]),
        '2Z': Polygon([(22, 7), (24, 7), (24, 9), (22, 9)]),
        '3A': Polygon([(24, 7), (26, 7), (26, 9), (24, 9)]),
        '3B': Polygon([(26, 7), (28, 7), (28, 9), (26, 9)]),

        # Central vertical line (3C–3H)
        '3C': Polygon([(14, 11), (16, 11), (16, 13), (14, 13)]),
        '3D': Polygon([(14, 9), (16, 9), (16, 11), (14, 11)]),
        '3E': Polygon([(14, 7), (16, 7), (16, 9), (14, 9)]),
        '3G': Polygon([(14, 5), (16, 5), (16, 7), (14, 7)]),
        '3H': Polygon([(14, 3), (16, 3), (16, 5), (14, 5)]),
    }
    # Add the exits to de dict
    for key, value in exit_polygons.items():
        specific_areas[key] = Polygon(value)

    floor = Floor(
        name="First floor",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        sources=sources,
        targets=targets,
        specific_areas=specific_areas
    )
    floors_dict = {0: floor}
    return Environment(
        name="comparing_algorithms",
        floors=floors_dict,
        graph=create_global_graph(floors_dict)
    )

def get_simple_3x3():
    complete_area = Polygon([(0, 0), (0, 15), (15, 15), (15, 0)])
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
            [(3.6, 4.9), (4.9, 4.9), (4.9, 3.6), (5.1, 3.6), (5.1, 4.9), (6.4, 4.9), (6.4, 5.1), (5.1, 5.1), (5.1, 6.5),
             (4.9, 6.5), (4.9, 5.1), (3.6, 5.1)]),
        ## bottom right
        Polygon([(8.6, 4.9), (9.9, 4.9), (9.9, 3.6), (10.1, 3.6), (10.1, 4.9), (11.5, 4.9), (11.5, 5.1), (10.1, 5.1),
                 (10.1, 6.5), (9.9, 6.5), (9.9, 5.1), (8.6, 5.1)]),
        ## top left
        Polygon([(3.6, 9.9), (4.9, 9.9), (4.9, 8.6), (5.1, 8.6), (5.1, 9.9), (6.4, 9.9), (6.4, 10.1), (5.1, 10.1),
                 (5.1, 11.5), (4.9, 11.5), (4.9, 10.1), (3.6, 10.1)]),
        ## top right
        Polygon([(8.6, 9.9), (9.9, 9.9), (9.9, 8.6), (10.1, 8.6), (10.1, 9.9), (11.5, 9.9), (11.5, 10.1), (10.1, 10.1),
                 (10.1, 11.5), (9.9, 11.5), (9.9, 10.1), (8.6, 10.1)]),

    ]
    exit_polygons = {'I': [(12.5, 12.5), (15, 12.5), (15, 15), (12.5, 15)]}

    waypoints = {
        'A': ([2.5, 2.5], 1.5),
        'B': ([7.5, 2.5], 1.5),
        'C': ([12.5, 2.5], 1.5),
        'D': ([12.5, 7.5], 1.5),
        'E': ([7.5, 7.5], 1.5),
        'F': ([2.5, 7.5], 1.5),
        'G': ([2.5, 12.5], 1.5),
        'H': ([7.5, 12.5], 1.5)
    }

    distribution_polygons = {'A': Polygon([[0, 0], [5, 0], [5, 5], [0, 5]])}

    # Create the graph
    G = nx.DiGraph()

    # Nodos y sus niveles iniciales de riesgo (0 a 1)
    nodes = {
        "A": 0.0, "B": 0.6, "C": 0.0,
        "D": 0.6, "E": 0.6, "F": 0.1,
        "G": 0.0, "H": 0.0, "I": 0.0,
    }

    # Agregar nodos al grafo
    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    G.nodes["I"]["is_stairs"] = True

    # Definir las conexiones entre nodos
    edges = [
        ("A", "B"), ("A", "F"), ("B", "A"), ("B", "E"), ("B", "C"),
        ("C", "B"), ("C", "D"), ("D", "I"), ("D", "E"), ("D", "C"),
        ("E", "D"), ("E", "F"), ("E", "B"), ("E", "H"), ("F", "A"),
        ("F", "E"), ("F", "G"), ("G", "F"), ("G", "H"), ("H", "E"),
        ("H", "G"), ("H", "I"),
    ]

    # Agregar las aristas con un costo fijo (se puede ajustar)
    G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])

    specific_areas = {
        'A': Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]),
        'B': Polygon([(5, 0), (10, 0), (10, 5), (5, 5)]),
        'C': Polygon([(10, 0), (15, 0), (15, 5), (10, 5)]),
        'D': Polygon([(10, 5), (15, 5), (15, 10), (10, 10)]),
        'E': Polygon([(5, 5), (10, 5), (10, 10), (5, 10)]),
        'F': Polygon([(0, 5), (5, 5), (5, 10), (0, 10)]),
        'G': Polygon([(0, 10), (5, 10), (5, 15), (0, 15)]),
        'H': Polygon([(5, 10), (10, 10), (10, 15), (5, 15)]),
        'I': Polygon([(10, 10), (15, 10), (15, 15), (10, 15)]),
    }

    # so that the walls are properly shown
    specific_areas = remove_obstacles_from_areas(specific_areas, obstacles)

    floor = Floor(
        name="First floor",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        sources=["A"],
        targets=["I"],
        specific_areas=specific_areas
    )
    floors_dict = {0: floor}
    return Environment(
        name="simple_3x3",
        floors=floors_dict,
        graph=create_global_graph(floors_dict)
    )

def get_multi_floor_3x3():
    complete_area = Polygon([(0, 0), (0, 15), (15, 15), (15, 0)])
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
            [(3.6, 4.9), (4.9, 4.9), (4.9, 3.6), (5.1, 3.6), (5.1, 4.9), (6.4, 4.9), (6.4, 5.1), (5.1, 5.1), (5.1, 6.5),
             (4.9, 6.5), (4.9, 5.1), (3.6, 5.1)]),
        ## bottom right
        Polygon([(8.6, 4.9), (9.9, 4.9), (9.9, 3.6), (10.1, 3.6), (10.1, 4.9), (11.5, 4.9), (11.5, 5.1), (10.1, 5.1),
                 (10.1, 6.5), (9.9, 6.5), (9.9, 5.1), (8.6, 5.1)]),
        ## top left
        Polygon([(3.6, 9.9), (4.9, 9.9), (4.9, 8.6), (5.1, 8.6), (5.1, 9.9), (6.4, 9.9), (6.4, 10.1), (5.1, 10.1),
                 (5.1, 11.5), (4.9, 11.5), (4.9, 10.1), (3.6, 10.1)]),
        ## top right
        Polygon([(8.6, 9.9), (9.9, 9.9), (9.9, 8.6), (10.1, 8.6), (10.1, 9.9), (11.5, 9.9), (11.5, 10.1), (10.1, 10.1),
                 (10.1, 11.5), (9.9, 11.5), (9.9, 10.1), (8.6, 10.1)]),

    ]

    exit_polygons = {'A': [(0, 0), (2.5, 0), (2.5, 2.5), (0, 2.5)]}

    waypoints = {
        'B': ([7.5, 2.5], 1.5),
        'C': ([12.5, 2.5], 1.5),
        'D': ([12.5, 7.5], 1.5),
        'E': ([7.5, 7.5], 1.5),
        'F': ([2.5, 7.5], 1.5),
        'G': ([2.5, 12.5], 1.5),
        'H': ([7.5, 12.5], 1.5),
        'I': ([12.5, 12.5], 1.5)
    }

    distribution_polygons = {'G': Polygon([(0, 10), (5, 10), (5, 15), (0, 15)])}

    # Create the graph
    G = nx.DiGraph()

    # Nodos y sus niveles iniciales de riesgo (0 a 1)
    nodes = {
        "A": 0.0, "B": 0.6, "C": 0.0,
        "D": 0.6, "E": 0.6, "F": 0.1,
        "G": 0.0, "H": 0.0, "I": 0.0,
    }

    # Agregar nodos al grafo
    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    G.nodes["I"]["is_stairs"] = True

    # Definir las conexiones entre nodos
    edges = [
        ("A", "B"), ("A", "F"), ("B", "A"), ("B", "E"), ("B", "C"),
        ("C", "B"), ("C", "D"), ("D", "I"), ("D", "E"), ("D", "C"),
        ("E", "D"), ("E", "F"), ("E", "B"), ("E", "H"), ("F", "A"),
        ("F", "E"), ("F", "G"), ("G", "F"), ("G", "H"), ("H", "E"),
        ("H", "G"), ("H", "I"),
    ]

    # Agregar las aristas con un costo fijo (se puede ajustar)
    G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])

    specific_areas = {
        'A': Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]),
        'B': Polygon([(5, 0), (10, 0), (10, 5), (5, 5)]),
        'C': Polygon([(10, 0), (15, 0), (15, 5), (10, 5)]),
        'D': Polygon([(10, 5), (15, 5), (15, 10), (10, 10)]),
        'E': Polygon([(5, 5), (10, 5), (10, 10), (5, 10)]),
        'F': Polygon([(0, 5), (5, 5), (5, 10), (0, 10)]),
        'G': Polygon([(0, 10), (5, 10), (5, 15), (0, 15)]),
        'H': Polygon([(5, 10), (10, 10), (10, 15), (5, 15)]),
        'I': Polygon([(10, 10), (15, 10), (15, 15), (10, 15)]),
    }

    # so that the walls are properly shown
    specific_areas = remove_obstacles_from_areas(specific_areas, obstacles)

    floor1 = Floor(
        name="First floor",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        sources=["G"],
        targets=["A"],
        specific_areas=specific_areas
    )

    ## SECOND FLOOR

    pref = "1"

    mapping = {node: f"{pref}_{node}" for node in floor1.graph.nodes()}
    G2 = nx.relabel_nodes(floor1.graph, mapping)
    for node in G2.nodes():
        G2.nodes[node]['floor'] = 1

    exit_polygons_2 = {f'{pref}_I': [(12.5, 12.5), (15, 12.5), (15, 15), (12.5, 15)]}

    waypoints_2 = {
        f'{pref}_A': ([2.5, 2.5], 1.5),
        f'{pref}_B': ([7.5, 2.5], 1.5),
        f'{pref}_C': ([12.5, 2.5], 1.5),
        f'{pref}_D': ([12.5, 7.5], 1.5),
        f'{pref}_E': ([7.5, 7.5], 1.5),
        f'{pref}_F': ([2.5, 7.5], 1.5),
        f'{pref}_G': ([2.5, 12.5], 1.5),
        f'{pref}_H': ([7.5, 12.5], 1.5),
    }

    specific_areas_2 = {mapping.get(key, key): area for key, area in floor1.specific_areas.items()}
    distribution_polygons_2 = {f'{pref}_A': floor1.specific_areas['A']}

    floor2 = Floor(
        name="Second floor",
        graph=G2,
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons_2,
        waypoints=waypoints_2,
        distribution_polygons=distribution_polygons_2,
        sources=[f"{pref}_A"],
        targets=[f"{pref}_I"],
        specific_areas=specific_areas_2
    )

    floors_dict = {0: floor1, 1: floor2}

    GlobG = create_global_graph(floors_dict)

    GlobG.add_edge(f"{pref}_I", "I", cost=0)

    return Environment(
        name="simple_3x3",
        floors=floors_dict,
        graph=GlobG
    )