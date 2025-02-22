from shapely.geometry import Polygon
import shapely  # Used for union_all and difference
import pedpy  # Ensure this module is installed
import networkx as nx

class Environment:
    """
    Class that encapsulates various sets of polygons and associated structures.

    Attributes:
        complete_area: Polygon defining the complete area.
        obstacles: List of Polygons representing obstacles.
        exit_polygons: Dictionary with exit polygons.
        waypoints: Dictionary with waypoints.
        distribution_polygons: Dictionary with distribution polygons.
        G: Some structure, e.g., a graph.
        sources: List or structure of source nodes.
        targets: List or structure of target nodes.
        specific_areas: Dictionary of specific areas.

    Additionally, if complete_area and obstacles are provided, the following are computed:
        obstacle: Union of all obstacles.
        walkable_area: Walkable area resulting from subtracting obstacle from complete_area,
                       wrapped in pedpy.WalkableArea.
    """

    def __init__(self, name, complete_area, obstacles, exit_polygons, waypoints,
                 distribution_polygons, G, sources, targets, specific_areas):
        self.name = name
        self.complete_area = complete_area
        self.obstacles = obstacles
        self.exit_polygons = exit_polygons
        self.waypoints = waypoints
        self.distribution_polygons = distribution_polygons
        self.G = G
        self.sources = sources
        self.targets = targets
        self.specific_areas = specific_areas

        # Compute derived attributes
        self.obstacle = shapely.union_all(self.obstacles)
        self.walkable_area = pedpy.WalkableArea(
            shapely.difference(self.complete_area, self.obstacle)
        )

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

        # Store the cleaned area in the dictionary
        cleaned_areas[name] = cleaned_area

    return cleaned_areas

def get_comparing_algorithms_pol():
    # Parameters for path calculation
    sources = ["C", "F"]  # Starting node for pathfinding
    targets = ["EA", "EB", "EC", "ED"]  # Target nodes for pathfinding

    complete_area = Polygon(
        [
            (0, -2),
            (0, 18),
            (32, 18),
            (32, -2),
        ]
    )
    obstacles = [
        # bottom
        Polygon([(0, -2), (14, -2), (14, 0), (0, 0)]),
        Polygon([(16, -2), (32, -2), (32, 0), (16, 0)]),

        # top
        Polygon([(0, 16), (14, 16), (14, 18), (0, 18)]),
        Polygon([(16, 16), (32, 16), (32, 18), (16, 18)]),

        Polygon([(2, 2), (14, 2), (14, 7), (2, 7)]),
        Polygon([(16, 2), (28, 2), (28, 7), (16, 7)]),
        Polygon([(2, 9), (14, 9), (14, 14), (2, 14)]),
        Polygon([(16, 9), (28, 9), (28, 14), (16, 14)]),

        Polygon([(30, 0), (32, 0), (32, 3.5), (30, 3.5)]),
        Polygon([(30, 5.5), (32, 5.5), (32, 10.5), (30, 10.5)]),
        Polygon([(30, 12.5), (32, 12.5), (32, 18), (30, 18)]),
    ]

    exit_polygons = {'EA': [(14, 0), (14, -2), (16, -2), (16, 0)], 'EB': [(14, 16), (14, 18), (16, 18), (16, 16)],
                     'EC': [(30, 3.5), (32, 3.5), (32, 5.5), (30, 5.5)],
                     'ED': [(30, 10.5), (32, 10.5), (32, 12.5), (30, 12.5)]}

    waypoints = {
        # left (8)
        'A': ([1, 15], 0.75),
        'B': ([1, 13], 0.75),
        'C': ([1, 11], 0.75),
        'D': ([1, 9], 0.75),
        'E': ([1, 7], 0.75),
        'F': ([1, 5], 0.75),
        'G': ([1, 3], 0.75),
        'H': ([1, 1], 0.75),
        # bottom (13)
        'I': ([3, 1], 0.75),
        'J': ([5, 1], 0.75),
        'K': ([7, 1], 0.75),
        'L': ([9, 1], 0.75),
        'M': ([11, 1], 0.75),
        'N': ([13, 1], 0.75),
        'O': ([15, 1], 0.75),
        'P': ([17, 1], 0.75),
        'Q': ([19, 1], 0.75),
        'R': ([21, 1], 0.75),
        'S': ([23, 1], 0.75),
        'T': ([25, 1], 0.75),
        'U': ([27, 1], 0.75),
        # right (8)
        'V': ([29, 15], 0.75),
        'W': ([29, 13], 0.75),
        'X': ([29, 11], 0.75),
        'Y': ([29, 9], 0.75),
        'Z': ([29, 7], 0.75),
        '2A': ([29, 5], 0.75),
        '2B': ([29, 3], 0.75),
        '2C': ([29, 1], 0.75),
        # top (13)
        '2D': ([3, 15], 0.75),
        '2E': ([5, 15], 0.75),
        '2F': ([7, 15], 0.75),
        '2G': ([9, 15], 0.75),
        '2H': ([11, 15], 0.75),
        '2I': ([13, 15], 0.75),
        '2J': ([15, 15], 0.75),
        '2K': ([17, 15], 0.75),
        '2L': ([19, 15], 0.75),
        '2M': ([21, 15], 0.75),
        '2N': ([23, 15], 0.75),
        '2O': ([25, 15], 0.75),
        '2P': ([27, 15], 0.75),
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
        '3C': ([15, 13], 0.75),
        '3D': ([15, 11], 0.75),
        '3E': ([15, 9], 0.75),
        '3F': ([15, 7], 0.75),
        '3G': ([15, 5], 0.75),
        '3H': ([15, 3], 0.75)
    }

    distribution_polygons = {
        'C': Polygon([(0, 10), (2, 10), (2, 12), (0, 12)]),
        'F': Polygon([(0, 4), (2, 4), (2, 6), (0, 6)]),
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
        'E': 0.0,
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
        'O': 0.0,
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
        'Z': 0.0,
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
        '3F': 0.0,
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
        G.add_node(node, risk=risk, blocked=False)

    # Define edges between nodes (directed connections)
    # Each tuple represents an edge: (from_node, to_node)
    edges = [

        # 1) OUTER PERIMETER
        # -- Left Side (A→H)
        ("A", "B"), ("B", "A"),
        ("B", "C"), ("C", "B"),
        ("C", "D"), ("D", "C"),
        ("D", "E"), ("E", "D"),
        ("E", "F"), ("F", "E"),
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
        ("2A", "Z"), ("Z", "2A"),
        ("Z", "Y"), ("Y", "Z"),
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
        ("2V", "2W"), ("2W", "2V"),
        ("2W", "2X"), ("2X", "2W"),
        ("2X", "2Y"), ("2Y", "2X"),
        ("2Y", "2Z"), ("2Z", "2Y"),
        ("2Z", "3A"), ("3A", "2Z"),
        ("3A", "3B"), ("3B", "3A"),

        # 3) CENTRAL VERTICAL LINE (3C→3H)
        ("3C", "3D"), ("3D", "3C"),
        ("3D", "3E"), ("3E", "3D"),
        ("3E", "3F"), ("3F", "3E"),
        ("3F", "3G"), ("3G", "3F"),
        ("3G", "3H"), ("3H", "3G"),

        # 4) CONNECTIONS FROM THE CENTRAL LINES TO THE PERIMETER
        ("2Q", "D"), ("D", "2Q"),
        ("2Q", "E"), ("E", "2Q"),

        ("2V", "3E"), ("3E", "2V"),
        ("2V", "3F"), ("3F", "2V"),

        ("2W", "3E"), ("3E", "2W"),
        ("2W", "3F"), ("3F", "2W"),

        ("3B", "Y"), ("Y", "3B"),
        ("3B", "Z"), ("Z", "3B"),

        # -- Connections from the central vertical line to the perimeter
        ("3C", "2J"), ("2J", "3C"),  # (15,13) <-> (15,15)
        ("3H", "O"), ("O", "3H"),  # (15,3)  <-> (15,1)

        # 5) CONNECTIONS WITH EXITS (based on geometric proximity)
        ("EA", "O"), ("O", "EA"),  # EA ~ (15,0)
        ("EB", "2J"), ("2J", "EB"),  # EB ~ (15,16)
        ("EC", "2A"), ("2A", "EC"),  # EC ~ (30,4.5)
        ("ED", "X"), ("X", "ED")  # ED ~ (30,11.5)

    ]

    # Add the edges to the graph with cost 2 as all the areas are at the same distance
    G.add_edges_from([(u, v, {"cost": 2}) for u, v in edges])

    specific_areas = {
        # Left side (A–H)
        'A': Polygon([(0, 14), (2, 14), (2, 16), (0, 16)]),
        'B': Polygon([(0, 12), (2, 12), (2, 14), (0, 14)]),
        'C': Polygon([(0, 10), (2, 10), (2, 12), (0, 12)]),
        'D': Polygon([(0, 8), (2, 8), (2, 10), (0, 10)]),
        'E': Polygon([(0, 6), (2, 6), (2, 8), (0, 8)]),
        'F': Polygon([(0, 4), (2, 4), (2, 6), (0, 6)]),
        'G': Polygon([(0, 2), (2, 2), (2, 4), (0, 4)]),
        'H': Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),

        # Bottom side (I–U)
        'I': Polygon([(2, 0), (4, 0), (4, 2), (2, 2)]),
        'J': Polygon([(4, 0), (6, 0), (6, 2), (4, 2)]),
        'K': Polygon([(6, 0), (8, 0), (8, 2), (6, 2)]),
        'L': Polygon([(8, 0), (10, 0), (10, 2), (8, 2)]),
        'M': Polygon([(10, 0), (12, 0), (12, 2), (10, 2)]),
        'N': Polygon([(12, 0), (14, 0), (14, 2), (12, 2)]),
        'O': Polygon([(14, 0), (16, 0), (16, 2), (14, 2)]),
        'P': Polygon([(16, 0), (18, 0), (18, 2), (16, 2)]),
        'Q': Polygon([(18, 0), (20, 0), (20, 2), (18, 2)]),
        'R': Polygon([(20, 0), (22, 0), (22, 2), (20, 2)]),
        'S': Polygon([(22, 0), (24, 0), (24, 2), (22, 2)]),
        'T': Polygon([(24, 0), (26, 0), (26, 2), (24, 2)]),
        'U': Polygon([(26, 0), (28, 0), (28, 2), (26, 2)]),

        # Right side (V–2C)
        'V': Polygon([(28, 14), (30, 14), (30, 16), (28, 16)]),
        'W': Polygon([(28, 12), (30, 12), (30, 14), (28, 14)]),
        'X': Polygon([(28, 10), (30, 10), (30, 12), (28, 12)]),
        'Y': Polygon([(28, 8), (30, 8), (30, 10), (28, 10)]),
        'Z': Polygon([(28, 6), (30, 6), (30, 8), (28, 8)]),
        '2A': Polygon([(28, 4), (30, 4), (30, 6), (28, 6)]),
        '2B': Polygon([(28, 2), (30, 2), (30, 4), (28, 4)]),
        '2C': Polygon([(28, 0), (30, 0), (30, 2), (28, 2)]),

        # Top side (2D–2P)
        '2D': Polygon([(2, 14), (4, 14), (4, 16), (2, 16)]),
        '2E': Polygon([(4, 14), (6, 14), (6, 16), (4, 16)]),
        '2F': Polygon([(6, 14), (8, 14), (8, 16), (6, 16)]),
        '2G': Polygon([(8, 14), (10, 14), (10, 16), (8, 16)]),
        '2H': Polygon([(10, 14), (12, 14), (12, 16), (10, 16)]),
        '2I': Polygon([(12, 14), (14, 14), (14, 16), (12, 16)]),
        '2J': Polygon([(14, 14), (16, 14), (16, 16), (14, 16)]),
        '2K': Polygon([(16, 14), (18, 14), (18, 16), (16, 16)]),
        '2L': Polygon([(18, 14), (20, 14), (20, 16), (18, 16)]),
        '2M': Polygon([(20, 14), (22, 14), (22, 16), (20, 16)]),
        '2N': Polygon([(22, 14), (24, 14), (24, 16), (22, 16)]),
        '2O': Polygon([(24, 14), (26, 14), (26, 16), (24, 16)]),
        '2P': Polygon([(26, 14), (28, 14), (28, 16), (26, 16)]),

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
        '3C': Polygon([(14, 12), (16, 12), (16, 14), (14, 14)]),
        '3D': Polygon([(14, 10), (16, 10), (16, 12), (14, 12)]),
        '3E': Polygon([(14, 8), (16, 8), (16, 10), (14, 10)]),
        '3F': Polygon([(14, 6), (16, 6), (16, 8), (14, 8)]),
        '3G': Polygon([(14, 4), (16, 4), (16, 6), (14, 6)]),
        '3H': Polygon([(14, 2), (16, 2), (16, 4), (14, 4)]),
    }
    # Add the exits to de dict
    for key, value in exit_polygons.items():
        specific_areas[key] = Polygon(value)

    return Environment(
        name="comparing_algorithms",
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        G=G,
        sources=sources,
        targets=targets,
        specific_areas=specific_areas
    )

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

    waypoints = {'A': ([2.5, 2.5], 1.5), 'B': ([7.5, 2.5], 1.5), 'C': ([12.5, 2.5], 1.5), 'D': ([12.5, 7.5], 1.5), 'E': ([7.5, 7.5], 1.5),
                 'F': ([2.5, 7.5], 1.5), 'G': ([2.5, 12.5], 1.5), 'H': ([7.5, 12.5], 1.5)}

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
        G.add_node(node, risk=risk)

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

    # Parameters for calculation
    sources = "A"  # Source nodes
    targets = ["I"]  # Target nodes

    specific_areas = dict()
    specific_areas['A'] = Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
    specific_areas['B'] = Polygon([(5, 0), (10, 0), (10, 5), (5, 5)])
    specific_areas['C'] = Polygon([(10, 0), (15, 0), (15, 5), (10, 5)])
    specific_areas['D'] = Polygon([(10, 5), (15, 5), (15, 10), (10, 10)])
    specific_areas['E'] = Polygon([(5, 5), (10, 5), (10, 10), (5, 10)])
    specific_areas['F'] = Polygon([(0, 5), (5, 5), (5, 10), (0, 10)])
    specific_areas['G'] = Polygon([(0, 10), (5, 10), (5, 15), (0, 15)])
    specific_areas['H'] = Polygon([(5, 10), (10, 10), (10, 15), (5, 15)])
    specific_areas['I'] = Polygon([(10, 10), (15, 10), (15, 15), (10, 15)])

    # so that the walls are properly shown
    specific_areas = remove_obstacles_from_areas(specific_areas, obstacles)

    return Environment(
        name="simple_3x3",
        complete_area=complete_area,
        obstacles=obstacles,
        exit_polygons=exit_polygons,
        waypoints=waypoints,
        distribution_polygons=distribution_polygons,
        G=G,
        sources=sources,
        targets=targets,
        specific_areas=specific_areas
    )