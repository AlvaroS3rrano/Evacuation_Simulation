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

    def __init__(self, name, floors, environment_exits, graph):
        self.name = name
        self.floors = floors  # List of Floor objects
        self.environment_exits = environment_exits
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

def get_floor_segment(path, env, floor_key):
    """
    Given a path from the global graph, returns the contiguous segment of the path
    that belongs to the specified floor.

    Once the agent leave a floor it is asumed it can´t go back to the same floor

    Parameters:
        path (list): A list of node names representing the path in the global graph.
        env (Environment): An Environment object that has a 'floors' attribute, a dictionary
                           where each key corresponds to a Floor object.
        floor_key: The key (or identifier) of the current floor.

    Returns:
        list: The sublist of the path that belongs to the specified floor.

    Raises:
        ValueError: If the provided floor_key does not exist in the environment.
    """
    if not path:
        return []

    # Get the specified floor.
    if floor_key not in env.floors:
        raise ValueError("The provided floor_key was not found in the environment.")

    current_floor = env.floors[floor_key]

    # Build the segment containing nodes only from the specified floor.
    segment = []
    for node in path:
        if node in current_floor.graph:
            segment.append(node)

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
        environment_exits=floor.exit_polygons.keys(),
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
        ("H", "G"), ("H", "I"), ("I", "D"), ("I", "H")
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
        environment_exits=floor.exit_polygons.keys(),
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
        ("H", "G"), ("H", "I"), ("I", "D"), ("I", "H")
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
        name="multi_floor_3x3",
        floors=floors_dict,
        environment_exits= floor1.exit_polygons.keys(),
        graph=GlobG
    )

def big_hall():
    complete_area = Polygon([(0, 0), (0, 50), (30, 50), (30, 0)])


    obstacles = [
        Polygon([(0, 4), (2, 4), (2, 10), (5, 10), (5, 45), (10, 45), (10, 48), (20,48), (20, 45), (25,45), (25, 4),
                 (30, 4), (30, 50), (0,50), (0, 4)]),

        Polygon([(4, 0), (23, 0), (23, 4), (10, 4), (10, 7), (4, 7)]), # 1

        Polygon([(7, 9), (10, 9), (10, 22.9), (10.5, 22.9), (10.5, 23), (9, 23), (9, 24), (7, 24)]), # 2

        Polygon([(20, 6),(23, 6), (23, 23), (19.5, 23), (19.5, 22.9), (20, 22.9)]),

        Polygon([(12, 6), (18, 6), (18, 11), (12, 11)]), # 3

        Polygon([(13, 13), (17, 13), (17, 19), (13, 19)]),

        Polygon([(13, 21), (17, 21), (17, 22.9), (17.5, 22.9), (17.5, 23), (17, 23), (12.5, 23), (12.5,22.9), (13, 22.9)]), # 4

        Polygon([(7, 41),(7, 35.5), (7.1, 35.5), (7.1 ,41), (14, 40.9), (14, 41), (12, 41), (12, 43), (7, 43)]),

        Polygon([(7, 33.5), (7, 26), (11, 26), (11, 25), (14, 25), (14, 25.1), (11.1, 25.1), (11.1, 26.1),
                 (7.1, 26.1), (7.1, 33.5)]),

        Polygon([(16, 25), (23, 25), (23, 29.5), (22.9, 29.5), (22.9, 25.1), (16, 25.1)]),

        Polygon([(22.9, 31.5), (23, 31.5), (23, 34.5), (22.9, 34.5)]),

        Polygon([(22.9, 36.5), (23, 36.5), (23, 43), (18, 43), (18, 41), (16, 41), (16, 40.9), (18.1, 40.9),
                 (18.1, 42.9), (22.9, 42.9)]),

        Polygon([(4, 2), (2, 2), (2, 2.1), (4, 2.1)]),

        Polygon([(23, 2), (28, 2), (28, 2.1), (23, 2.1)]),
    ]

    exit_polygons = {
        '1': Polygon([(2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0)]),
        '55': Polygon([(23.0, 0.0), (25.0, 0.0), (25.0, 2.0), (23.0, 2.0)]),
    }

    waypoints = {
        #'1': ([3.0, 1.0], 0.5),
        '2': ([1.0, 1.0], 0.5),
        '3': ([1.0, 3.0], 0.5),
        '4': ([3.0, 3.0], 0.5),
        '5': ([3.0, 5.5], 0.5),
        '6': ([3.5, 8.5], 1.0),
        '7': ([6.0, 8.5], 0.5),
        '8': ([6.0, 11.5], 0.5),
        '9': ([6.0, 14.0], 0.5),
        '10': ([6.0, 16.0], 0.5),
        '11': ([6.0, 18.0], 0.5),
        '12': ([6.0, 20.0], 0.5),
        '13': ([6.0, 22.0], 0.5),
        '14': ([6.0, 24.5], 0.5),
        '15': ([6.0, 27.5], 0.5),
        '16': ([6.0, 30.0], 0.5),
        '17': ([6.0, 32.0], 0.5),
        '18': ([6.0, 34.5], 0.5),
        '19': ([6.0, 37.5], 0.5),
        '20': ([6.0, 40.0], 0.5),
        '21': ([6.0, 42.0], 0.5),
        '22': ([6.0, 44.0], 0.5),
        '23': ([8.5, 8.0], 0.5),
        '24': ([11.0, 8.0], 0.5),
        '25': ([11.0, 5.5], 0.5),
        '26': ([13.0, 5.0], 0.5),
        '27': ([15.0, 5.0], 0.5),
        '28': ([17.0, 5.0], 0.5),
        '29': ([19.0, 5.5], 0.5),
        '30': ([21.0, 5.0], 0.5),
        '31': ([23.5, 5.0], 0.5),
        '32': ([24.0, 7.5], 0.5),
        '33': ([24.0, 10.0], 0.5),
        '34': ([24.0, 12.0], 0.5),
        '35': ([24.0, 14.0], 0.5),
        '36': ([24.0, 16.0], 0.5),
        '37': ([24.0, 18.0], 0.5),
        '38': ([24.0, 20.0], 0.5),
        '39': ([24.0, 22.0], 0.5),
        '40': ([24.0, 24.0], 0.5),
        '41': ([24.0, 26.0], 0.5),
        '42': ([24.0, 28.0], 0.5),
        '43': ([24.0, 30.5], 0.5),
        '44': ([24.0, 33.0], 0.5),
        '45': ([24.0, 35.5], 0.5),
        '46': ([24.0, 38.0], 0.5),
        '47': ([24.0, 40.0], 0.5),
        '48': ([24.0, 42.0], 0.5),
        '49': ([24.0, 44.0], 0.5),
        '50': ([24.0, 3.0], 0.5),
        '51': ([26.5, 3.0], 0.5),
        '52': ([29.0, 3.0], 0.5),
        '53': ([29.0, 1.0], 0.5),
        '54': ([26.5, 1.0], 0.5),
        #'55': ([24.0, 1.0], 0.5),
        '56': ([11.0, 10.0], 0.5),
        '57': ([11.5, 12.0], 0.5),
        '58': ([11.5, 14.0], 0.5),
        '59': ([11.5, 16.0], 0.5),
        '60': ([11.5, 18.0], 0.5),
        '61': ([11.5, 20.0], 0.5),
        '62': ([11.5, 22.0], 0.5),
        '63': ([14.0, 12.0], 0.5),
        '64': ([16.0, 12.0], 0.5),
        '65': ([14.0, 20.0], 0.5),
        '66': ([16.0, 20.0], 0.5),
        '67': ([19.0, 8.0], 0.5),
        '68': ([19.0, 10.0], 0.5),
        '69': ([18.5, 12.0], 0.5),
        '70': ([18.5, 14.0], 0.5),
        '71': ([18.5, 16.0], 0.5),
        '72': ([18.5, 18.0], 0.5),
        '73': ([18.5, 20.0], 0.5),
        '74': ([18.5, 22.0], 0.5),
        '75': ([8.0, 25.0], 0.5),
        '76': ([10.0, 24.5], 0.5),
        '77': ([12.0, 24.0], 0.5),
        '78': ([15.0, 24.0], 0.5),
        '79': ([18.5, 24.0], 0.5),
        '80': ([21.5, 24.0], 0.5),
        '81': ([8.5, 44.0], 0.5),
        '82': ([12.5, 45.5], 2.5),
        '83': ([17.5, 45.5], 2.5),
        '84': ([15.0, 42.0], 0.75),
        '85': ([21.5, 44.0], 0.5),
        '86': ([9.0, 27.5], 1.5),
        '87': ([9.0, 30.5], 1.5),
        '88': ([9.0, 34.0], 1.5),
        '89': ([9.0, 37.0], 0.75),
        '90': ([9.0, 39.5], 1.5),
        '91': ([14.0, 27.0], 1.5),
        '92': ([14.0, 31.0], 1.5),
        '93': ([14.0, 35.0], 1.5),
        '94': ([14.0, 39.0], 1.5),
        '95': ([20.0, 27.0], 1.5),
        '96': ([20.0, 31.0], 1.5),
        '97': ([20.0, 35.0], 1.5),
        '98': ([20.0, 39.0], 1.5),
        '99': ([20.5, 42.0], 0.5),
    }

    distribution_polygons = {
        '82': Polygon([(10.0, 43.0), (15.0, 43.0), (15.0, 48.0), (10.0, 48.0)]),
    }

    G = nx.DiGraph()

    nodes = {
        "1": 0.0,
        "2": 0.0,
        "3": 0.0,
        "4": 0.0,
        "5": 0.0,
        "6": 0.0,
        "7": 0.0,
        "8": 0.0,
        "9": 0.0,
        "10": 0.0,
        "11": 0.0,
        "12": 0.0,
        "13": 0.0,
        "14": 0.0,
        "15": 0.0,
        "16": 0.0,
        "17": 0.0,
        "18": 0.0,
        "19": 0.0,
        "20": 0.0,
        "21": 0.0,
        "22": 0.0,
        "23": 0.0,
        "24": 0.0,
        "25": 0.0,
        "26": 0.0,
        "27": 0.0,
        "28": 0.0,
        "29": 0.0,
        "30": 0.0,
        "31": 0.0,
        "32": 0.0,
        "33": 0.0,
        "34": 0.0,
        "35": 0.0,
        "36": 0.0,
        "37": 0.0,
        "38": 0.0,
        "39": 0.0,
        "40": 0.0,
        "41": 0.0,
        "42": 0.0,
        "43": 0.0,
        "44": 0.0,
        "45": 0.0,
        "46": 0.0,
        "47": 0.0,
        "48": 0.0,
        "49": 0.0,
        "50": 0.0,
        "51": 0.0,
        "52": 0.0,
        "53": 0.0,
        "54": 0.0,
        "55": 0.0,
        "56": 0.0,
        "57": 0.0,
        "58": 0.0,
        "59": 0.0,
        "60": 0.0,
        "61": 0.0,
        "62": 0.0,
        "63": 0.0,
        "64": 0.0,
        "65": 0.0,
        "66": 0.0,
        "67": 0.0,
        "68": 0.0,
        "69": 0.0,
        "70": 0.0,
        "71": 0.0,
        "72": 0.0,
        "73": 0.0,
        "74": 0.0,
        "75": 0.0,
        "76": 0.0,
        "77": 0.0,
        "78": 0.0,
        "79": 0.0,
        "80": 0.0,
        "81": 0.0,
        "82": 0.0,
        "83": 0.0,
        "84": 0.0,
        "85": 0.0,
        "86": 0.0,
        "87": 0.0,
        "88": 0.0,
        "89": 0.0,
        "90": 0.0,
        "91": 0.0,
        "92": 0.0,
        "93": 0.0,
        "94": 0.0,
        "95": 0.0,
        "96": 0.0,
        "97": 0.0,
        "98": 0.0,
        "99": 0.0,
    }

    for node, risk in nodes.items():
        G.add_node(node, risk=risk, blocked=False, is_stairs=False, floor=0)

    G.nodes["1"]["is_stairs"] = True
    G.nodes["2"]["is_stairs"] = True
    G.nodes["3"]["is_stairs"] = True
    G.nodes["4"]["is_stairs"] = True
    G.nodes["50"]["is_stairs"] = True
    G.nodes["51"]["is_stairs"] = True
    G.nodes["52"]["is_stairs"] = True
    G.nodes["53"]["is_stairs"] = True
    G.nodes["54"]["is_stairs"] = True
    G.nodes["54"]["is_stairs"] = True

    edges = [
        ('1', '2'),
        ('2', '1'),
        ('2', '3'),
        ('3', '2'),
        ('3', '4'),
        ('4', '3'),
        ('4', '5'),
        ('5', '4'),
        ('5', '6'),
        ('6', '5'),
        ('6', '7'),
        ('7', '6'),
        ('7', '8'),
        ('7', '23'),
        ('8', '7'),
        ('8', '9'),
        ('9', '8'),
        ('9', '10'),
        ('10', '9'),
        ('10', '11'),
        ('11', '10'),
        ('11', '12'),
        ('12', '11'),
        ('12', '13'),
        ('13', '12'),
        ('13', '14'),
        ('14', '13'),
        ('14', '15'),
        ('14', '75'),
        ('15', '14'),
        ('15', '16'),
        ('16', '15'),
        ('16', '17'),
        ('17', '16'),
        ('17', '18'),
        ('18', '17'),
        ('18', '19'),
        ('18', '88'),
        ('19', '18'),
        ('19', '20'),
        ('20', '19'),
        ('20', '21'),
        ('21', '20'),
        ('21', '22'),
        ('22', '21'),
        ('22', '81'),
        ('23', '7'),
        ('23', '24'),
        ('24', '23'),
        ('24', '25'),
        ('24', '56'),
        ('25', '24'),
        ('25', '26'),
        ('26', '25'),
        ('26', '27'),
        ('27', '26'),
        ('27', '28'),
        ('28', '27'),
        ('28', '29'),
        ('29', '28'),
        ('29', '30'),
        ('29', '67'),
        ('30', '29'),
        ('30', '31'),
        ('31', '30'),
        ('31', '32'),
        ('31', '50'),
        ('32', '31'),
        ('32', '33'),
        ('33', '32'),
        ('33', '34'),
        ('34', '33'),
        ('34', '35'),
        ('35', '34'),
        ('35', '36'),
        ('36', '35'),
        ('36', '37'),
        ('37', '36'),
        ('37', '38'),
        ('38', '37'),
        ('38', '39'),
        ('39', '38'),
        ('39', '40'),
        ('40', '39'),
        ('40', '41'),
        ('40', '80'),
        ('41', '40'),
        ('41', '42'),
        ('42', '41'),
        ('42', '43'),
        ('43', '42'),
        ('43', '44'),
        ('43', '96'),
        ('44', '43'),
        ('44', '45'),
        ('45', '44'),
        ('45', '46'),
        ('45', '97'),
        ('46', '45'),
        ('46', '47'),
        ('47', '46'),
        ('47', '48'),
        ('48', '47'),
        ('48', '49'),
        ('49', '48'),
        ('49', '85'),
        ('50', '31'),
        ('50', '51'),
        ('51', '50'),
        ('51', '52'),
        ('52', '51'),
        ('52', '53'),
        ('53', '52'),
        ('53', '54'),
        ('54', '50'),
        ('54', '53'),
        ('54', '55'),
        ('55', '54'),
        ('56', '24'),
        ('56', '57'),
        ('57', '56'),
        ('57', '58'),
        ('57', '63'),
        ('58', '57'),
        ('58', '59'),
        ('59', '58'),
        ('59', '60'),
        ('60', '59'),
        ('60', '61'),
        ('61', '60'),
        ('61', '62'),
        ('61', '65'),
        ('62', '61'),
        ('62', '77'),
        ('63', '57'),
        ('63', '64'),
        ('64', '63'),
        ('64', '69'),
        ('65', '61'),
        ('65', '66'),
        ('66', '65'),
        ('66', '73'),
        ('67', '29'),
        ('67', '68'),
        ('68', '67'),
        ('68', '69'),
        ('69', '64'),
        ('69', '68'),
        ('69', '70'),
        ('70', '69'),
        ('70', '71'),
        ('71', '70'),
        ('71', '72'),
        ('72', '71'),
        ('72', '73'),
        ('73', '66'),
        ('73', '72'),
        ('73', '74'),
        ('74', '73'),
        ('74', '79'),
        ('75', '14'),
        ('75', '76'),
        ('76', '75'),
        ('76', '77'),
        ('77', '62'),
        ('77', '76'),
        ('77', '78'),
        ('78', '77'),
        ('78', '79'),
        ('78', '91'),
        ('79', '74'),
        ('79', '78'),
        ('79', '80'),
        ('80', '40'),
        ('80', '79'),
        ('81', '22'),
        ('81', '82'),
        ('82', '81'),
        ('82', '83'),
        ('82', '84'),
        ('83', '82'),
        ('83', '84'),
        ('83', '85'),
        ('84', '82'),
        ('84', '83'),
        ('84', '94'),
        ('85', '49'),
        ('85', '83'),
        ('86', '87'),
        ('86', '91'),
        ('87', '86'),
        ('87', '88'),
        ('87', '92'),
        ('88', '18'),
        ('88', '87'),
        ('88', '89'),
        ('88', '92'),
        ('88', '93'),
        ('89', '88'),
        ('89', '90'),
        ('89', '93'),
        ('89', '94'),
        ('90', '89'),
        ('90', '94'),
        ('91', '78'),
        ('91', '86'),
        ('91', '92'),
        ('91', '95'),
        ('92', '87'),
        ('92', '88'),
        ('92', '91'),
        ('92', '93'),
        ('92', '96'),
        ('93', '88'),
        ('93', '89'),
        ('93', '92'),
        ('93', '94'),
        ('93', '97'),
        ('94', '84'),
        ('94', '89'),
        ('94', '90'),
        ('94', '93'),
        ('94', '98'),
        ('95', '91'),
        ('95', '96'),
        ('96', '43'),
        ('96', '92'),
        ('96', '95'),
        ('96', '97'),
        ('97', '45'),
        ('97', '93'),
        ('97', '96'),
        ('97', '98'),
        ('98', '94'),
        ('98', '97'),
        ('98', '99'),
        ('99', '98'),
    ]

    G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])

    specific_areas = {
        '1': Polygon([(2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0)]),
        '2': Polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]),
        '3': Polygon([(0.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0)]),
        '4': Polygon([(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 4.0)]),
        '5': Polygon([(2.0, 4.0), (4.0, 4.0), (4.0, 7.0), (2.0, 7.0)]),
        '6': Polygon([(2.0, 7.0), (5.0, 7.0), (5.0, 10.0), (2.0, 10.0)]),
        '7': Polygon([(5.0, 7.0), (7.0, 7.0), (7.0, 10.0), (5.0, 10.0)]),
        '8': Polygon([(5.0, 10.0), (7.0, 10.0), (7.0, 13.0), (5.0, 13.0)]),
        '9': Polygon([(5.0, 13.0), (7.0, 13.0), (7.0, 15.0), (5.0, 15.0)]),
        '10': Polygon([(5.0, 15.0), (7.0, 15.0), (7.0, 17.0), (5.0, 17.0)]),
        '11': Polygon([(5.0, 17.0), (7.0, 17.0), (7.0, 19.0), (5.0, 19.0)]),
        '12': Polygon([(5.0, 19.0), (7.0, 19.0), (7.0, 21.0), (5.0, 21.0)]),
        '13': Polygon([(5.0, 21.0), (7.0, 21.0), (7.0, 23.0), (5.0, 23.0)]),
        '14': Polygon([(5.0, 23.0), (7.0, 23.0), (7.0, 26.0), (5.0, 26.0)]),
        '15': Polygon([(5.0, 26.0), (7.0, 26.0), (7.0, 29.0), (5.0, 29.0)]),
        '16': Polygon([(5.0, 29.0), (7.0, 29.0), (7.0, 31.0), (5.0, 31.0)]),
        '17': Polygon([(5.0, 31.0), (7.0, 31.0), (7.0, 33.0), (5.0, 33.0)]),
        '18': Polygon([(5.0, 33.0), (7.0, 33.0), (7.0, 36.0), (5.0, 36.0)]),
        '19': Polygon([(5.0, 36.0), (7.0, 36.0), (7.0, 39.0), (5.0, 39.0)]),
        '20': Polygon([(5.0, 39.0), (7.0, 39.0), (7.0, 41.0), (5.0, 41.0)]),
        '21': Polygon([(5.0, 41.0), (7.0, 41.0), (7.0, 43.0), (5.0, 43.0)]),
        '22': Polygon([(5.0, 43.0), (7.0, 43.0), (7.0, 45.0), (5.0, 45.0)]),
        '23': Polygon([(7.0, 7.0), (10.0, 7.0), (10.0, 9.0), (7.0, 9.0)]),
        '24': Polygon([(10.0, 7.0), (12.0, 7.0), (12.0, 9.0), (10.0, 9.0)]),
        '25': Polygon([(10.0, 4.0), (12.0, 4.0), (12.0, 7.0), (10.0, 7.0)]),
        '26': Polygon([(12.0, 4.0), (14.0, 4.0), (14.0, 6.0), (12.0, 6.0)]),
        '27': Polygon([(14.0, 4.0), (16.0, 4.0), (16.0, 6.0), (14.0, 6.0)]),
        '28': Polygon([(16.0, 4.0), (18.0, 4.0), (18.0, 6.0), (16.0, 6.0)]),
        '29': Polygon([(18.0, 4.0), (20.0, 4.0), (20.0, 7.0), (18.0, 7.0)]),
        '30': Polygon([(20.0, 4.0), (22.0, 4.0), (22.0, 6.0), (20.0, 6.0)]),
        '31': Polygon([(22.0, 4.0), (25.0, 4.0), (25.0, 6.0), (22.0, 6.0)]),
        '32': Polygon([(23.0, 6.0), (25.0, 6.0), (25.0, 9.0), (23.0, 9.0)]),
        '33': Polygon([(23.0, 9.0), (25.0, 9.0), (25.0, 11.0), (23.0, 11.0)]),
        '34': Polygon([(23.0, 11.0), (25.0, 11.0), (25.0, 13.0), (23.0, 13.0)]),
        '35': Polygon([(23.0, 13.0), (25.0, 13.0), (25.0, 15.0), (23.0, 15.0)]),
        '36': Polygon([(23.0, 15.0), (25.0, 15.0), (25.0, 17.0), (23.0, 17.0)]),
        '37': Polygon([(23.0, 17.0), (25.0, 17.0), (25.0, 19.0), (23.0, 19.0)]),
        '38': Polygon([(23.0, 19.0), (25.0, 19.0), (25.0, 21.0), (23.0, 21.0)]),
        '39': Polygon([(23.0, 21.0), (25.0, 21.0), (25.0, 23.0), (23.0, 23.0)]),
        '40': Polygon([(23.0, 23.0), (25.0, 23.0), (25.0, 25.0), (23.0, 25.0)]),
        '41': Polygon([(23.0, 25.0), (25.0, 25.0), (25.0, 27.0), (23.0, 27.0)]),
        '42': Polygon([(23.0, 27.0), (25.0, 27.0), (25.0, 29.0), (23.0, 29.0)]),
        '43': Polygon([(23.0, 29.0), (25.0, 29.0), (25.0, 32.0), (23.0, 32.0)]),
        '44': Polygon([(23.0, 32.0), (25.0, 32.0), (25.0, 34.0), (23.0, 34.0)]),
        '45': Polygon([(23.0, 34.0), (25.0, 34.0), (25.0, 37.0), (23.0, 37.0)]),
        '46': Polygon([(23.0, 37.0), (25.0, 37.0), (25.0, 39.0), (23.0, 39.0)]),
        '47': Polygon([(23.0, 39.0), (25.0, 39.0), (25.0, 41.0), (23.0, 41.0)]),
        '48': Polygon([(23.0, 41.0), (25.0, 41.0), (25.0, 43.0), (23.0, 43.0)]),
        '49': Polygon([(23.0, 43.0), (25.0, 43.0), (25.0, 45.0), (23.0, 45.0)]),
        '50': Polygon([(23.0, 2.0), (25.0, 2.0), (25.0, 4.0), (23.0, 4.0)]),
        '51': Polygon([(25.0, 2.0), (28.0, 2.0), (28.0, 4.0), (25.0, 4.0)]),
        '52': Polygon([(28.0, 2.0), (30.0, 2.0), (30.0, 4.0), (28.0, 4.0)]),
        '53': Polygon([(28.0, 0.0), (30.0, 0.0), (30.0, 2.0), (28.0, 2.0)]),
        '54': Polygon([(25.0, 0.0), (28.0, 0.0), (28.0, 2.0), (25.0, 2.0)]),
        '55': Polygon([(23.0, 0.0), (25.0, 0.0), (25.0, 2.0), (23.0, 2.0)]),
        '56': Polygon([(10.0, 9.0), (12.0, 9.0), (12.0, 11.0), (10.0, 11.0)]),
        '57': Polygon([(10.0, 11.0), (13.0, 11.0), (13.0, 13.0), (10.0, 13.0)]),
        '58': Polygon([(10.0, 13.0), (13.0, 13.0), (13.0, 15.0), (10.0, 15.0)]),
        '59': Polygon([(10.0, 15.0), (13.0, 15.0), (13.0, 17.0), (10.0, 17.0)]),
        '60': Polygon([(10.0, 17.0), (13.0, 17.0), (13.0, 19.0), (10.0, 19.0)]),
        '61': Polygon([(10.0, 19.0), (13.0, 19.0), (13.0, 21.0), (10.0, 21.0)]),
        '62': Polygon([(10.0, 21.0), (13.0, 21.0), (13.0, 23.0), (10.0, 23.0)]),
        '63': Polygon([(13.0, 11.0), (15.0, 11.0), (15.0, 13.0), (13.0, 13.0)]),
        '64': Polygon([(15.0, 11.0), (17.0, 11.0), (17.0, 13.0), (15.0, 13.0)]),
        '65': Polygon([(13.0, 19.0), (15.0, 19.0), (15.0, 21.0), (13.0, 21.0)]),
        '66': Polygon([(15.0, 19.0), (17.0, 19.0), (17.0, 21.0), (15.0, 21.0)]),
        '67': Polygon([(18.0, 7.0), (20.0, 7.0), (20.0, 9.0), (18.0, 9.0)]),
        '68': Polygon([(18.0, 9.0), (20.0, 9.0), (20.0, 11.0), (18.0, 11.0)]),
        '69': Polygon([(17.0, 11.0), (20.0, 11.0), (20.0, 13.0), (17.0, 13.0)]),
        '70': Polygon([(17.0, 13.0), (20.0, 13.0), (20.0, 15.0), (17.0, 15.0)]),
        '71': Polygon([(17.0, 15.0), (20.0, 15.0), (20.0, 17.0), (17.0, 17.0)]),
        '72': Polygon([(17.0, 17.0), (20.0, 17.0), (20.0, 19.0), (17.0, 19.0)]),
        '73': Polygon([(17.0, 19.0), (20.0, 19.0), (20.0, 21.0), (17.0, 21.0)]),
        '74': Polygon([(17.0, 21.0), (20.0, 21.0), (20.0, 23.0), (17.0, 23.0)]),
        '75': Polygon([(7.0, 24.0), (9.0, 24.0), (9.0, 26.0), (7.0, 26.0)]),
        '76': Polygon([(9.0, 23.0), (11.0, 23.0), (11.0, 26.0), (9.0, 26.0)]),
        '77': Polygon([(11.0, 23.0), (13.0, 23.0), (13.0, 25.0), (11.0, 25.0)]),
        '78': Polygon([(13.0, 23.0), (17.0, 23.0), (17.0, 25.0), (13.0, 25.0)]),
        '79': Polygon([(17.0, 23.0), (20.0, 23.0), (20.0, 25.0), (17.0, 25.0)]),
        '80': Polygon([(20.0, 23.0), (23.0, 23.0), (23.0, 25.0), (20.0, 25.0)]),
        '81': Polygon([(7.0, 43.0), (10.0, 43.0), (10.0, 45.0), (7.0, 45.0)]),
        '82': Polygon([(10.0, 43.0), (15.0, 43.0), (15.0, 48.0), (10.0, 48.0)]),
        '83': Polygon([(15.0, 43.0), (20.0, 43.0), (20.0, 48.0), (15.0, 48.0)]),
        '84': Polygon([(12.0, 41.0), (18.0, 41.0), (18.0, 43.0), (12.0, 43.0)]),
        '85': Polygon([(20.0, 43.0), (23.0, 43.0), (23.0, 45.0), (20.0, 45.0)]),
        '86': Polygon([(7.0, 26.0), (11.0, 26.0), (11.0, 29.0), (7.0, 29.0)]),
        '87': Polygon([(7.0, 29.0), (11.0, 29.0), (11.0, 32.0), (7.0, 32.0)]),
        '88': Polygon([(7.0, 32.0), (11.0, 32.0), (11.0, 36.0), (7.0, 36.0)]),
        '89': Polygon([(7.0, 36.0), (11.0, 36.0), (11.0, 38.0), (7.0, 38.0)]),
        '90': Polygon([(7.0, 38.0), (11.0, 38.0), (11.0, 41.0), (7.0, 41.0)]),
        '91': Polygon([(11.0, 25.0), (17.0, 25.0), (17.0, 29.0), (11.0, 29.0)]),
        '92': Polygon([(11.0, 29.0), (17.0, 29.0), (17.0, 33.0), (11.0, 33.0)]),
        '93': Polygon([(11.0, 33.0), (17.0, 33.0), (17.0, 37.0), (11.0, 37.0)]),
        '94': Polygon([(11.0, 37.0), (17.0, 37.0), (17.0, 41.0), (11.0, 41.0)]),
        '95': Polygon([(17.0, 25.0), (23.0, 25.0), (23.0, 29.0), (17.0, 29.0)]),
        '96': Polygon([(17.0, 29.0), (23.0, 29.0), (23.0, 33.0), (17.0, 33.0)]),
        '97': Polygon([(17.0, 33.0), (23.0, 33.0), (23.0, 37.0), (17.0, 37.0)]),
        '98': Polygon([(17.0, 37.0), (23.0, 37.0), (23.0, 41.0), (17.0, 41.0)]),
        '99': Polygon([(18.0, 41.0), (23.0, 41.0), (23.0, 43.0), (18.0, 43.0)]),
    }

    floor1 = Floor(
        name="First floor",
        graph=G,
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        sources=["82"],
        targets=["1", "55"],
        specific_areas=specific_areas
    )

    floors_dict = {0: floor1}

    return Environment(
        name="big_hall",
        floors=floors_dict,
        environment_exits=floor1.exit_polygons.keys(),
        graph=G
    )
