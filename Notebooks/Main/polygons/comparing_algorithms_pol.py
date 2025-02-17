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

    waypoints = {'A': ([1, 11.5], 1), 'B': ([1, 8], 1), 'C': ([1, 4.5], 1), 'D': ([1, 1], 1), 'E': ([8, 1], 1),
                 'F': ([15, 1], 1), 'G': ([22, 1], 1), 'H': ([29, 1], 1), 'I': ([29, 4.5], 1), 'J': ([29, 8], 1),
                 'K': ([29, 11.5], 1), 'L': ([29, 15], 1), 'M': ([22, 15], 1), 'N': ([15, 15], 1), 'O': ([8, 15], 1),
                 'P': ([1, 15], 1), 'Q': ([8, 8], 1), 'R': ([15, 8], 1), 'S': ([22, 8], 1), 'T': ([15, 11.5], 1),
                 'U': ([15, 4.5], 1)}
    distribution_polygons = {
        'A': Polygon([[0, 9], [2, 9], [2, 14], [0, 14]]),
        'C': Polygon([[0, 2], [2, 2], [2, 7], [0, 7]]),
    }

    G = nx.DiGraph()

    # Define nodes with their initial risk levels (0 to 1) and associated costs
    # Format: "Node": (risk_level, cost)
    nodes = {
        "A": (0.0, 5), "B": (0.0, 2), "C": (0.0, 5),
        "D": (0.0, 2), "E": (0.0, 5), "F": (0.5, 2),
        "G": (0.0, 5), "H": (0.0, 2), "I": (0.0, 5),
        "J": (0.0, 2), "K": (0.0, 5), "L": (0.0, 2),
        "M": (0.0, 5), "N": (0.0, 2), "O": (0.0, 5),
        "P": (0.4, 2), "Q": (0.0, 2), "R": (0.0, 2),
        "S": (0.0, 5), "T": (0.0, 5), "U": (0.0, 5),
        "EA": (0.0, 0), "EB": (0.0, 0), "EC": (0.0, 0),
        "ED": (0.0, 0),
    }

    # Add nodes to the graph with their attributes
    for node, (risk, cost) in nodes.items():
        G.add_node(node, risk=risk, blocked=False)

    # Define edges between nodes (directed connections)
    # Each tuple represents an edge: (from_node, to_node)
    edges = [
        ("P", "A"), ("P", "O"),
        ("A", "P"), ("A", "B"),
        ("B", "A"), ("B", "C"), ("B", "Q"),
        ("C", "B"), ("C", "D"),
        ("D", "C"), ("D", "E"),
        ("E", "D"), ("E", "F"),
        ("F", "E"), ("F", "G"), ("F", "U"), ("F", "EA"),
        ("G", "F"), ("G", "H"),
        ("H", "G"), ("H", "I"),
        ("I", "H"), ("I", "J"), ("I", "EC"),
        ("J", "I"), ("J", "K"), ("J", "S"),
        ("K", "J"), ("K", "L"), ("K", "ED"),
        ("L", "K"), ("L", "M"),
        ("M", "L"), ("M", "N"),
        ("N", "M"), ("N", "T"), ("N", "O"), ("N", "EB"),
        ("T", "N"), ("T", "R"),
        ("R", "T"), ("R", "Q"), ("R", "S"), ("R", "U"),
        ("Q", "B"), ("Q", "R"),
        ("S", "R"), ("S", "J"),
        ("O", "P"), ("O", "N"),
        ("U", "F"), ("U", "R"),
    ]

    # Add edges to the graph with a weight equal to the sum of the costs from both connected nodes.
    # For example, for the edge ("P", "A"):
    #   - The cost of "P" is 2
    #   - The cost of "A" is 5
    #   - Weight = 2 + 5 = 7
    for u, v in edges:
        # Retrieve the cost of each node from the original dictionary
        cost_u = nodes[u][1]
        cost_v = nodes[v][1]
        weight = cost_u + cost_v
        G.add_edge(u, v, cost=weight)

    # Parameters for path calculation
    sources = ["A", "C"]  # Starting node for pathfinding
    targets = ["EA", "EB", "EC", "ED"]  # Target nodes for pathfinding

    specific_areas = dict()
    specific_areas.update(distribution_polygons)
    specific_areas['B'] = Polygon([(0, 7), (2, 7), (2, 9), (0, 9)])
    specific_areas['D'] = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    specific_areas['E'] = Polygon([(2, 0), (14, 0), (14, 2), (2, 2)])
    specific_areas['F'] = Polygon([(14, 0), (16, 0), (16, 2), (14, 2)])
    specific_areas['G'] = Polygon([(16, 0), (28, 0), (28, 2), (16, 2)])
    specific_areas['H'] = Polygon([(28, 0), (30, 0), (30, 2), (28, 2)])
    specific_areas['I'] = Polygon([(28, 2), (30, 2), (30, 7), (28, 7)])
    specific_areas['J'] = Polygon([(28, 7), (30, 7), (30, 9), (28, 9)])
    specific_areas['K'] = Polygon([(28, 9), (30, 9), (30, 14), (28, 14)])
    specific_areas['L'] = Polygon([(28, 14), (30, 14), (30, 16), (28, 16)])
    specific_areas['M'] = Polygon([(16, 14), (28, 14), (28, 16), (16, 16)])
    specific_areas['N'] = Polygon([(14, 14), (16, 14), (16, 16), (14, 16)])
    specific_areas['O'] = Polygon([(2, 14), (14, 14), (14, 16), (2, 16)])
    specific_areas['P'] = Polygon([(0, 14), (2, 14), (2, 16), (0, 16)])
    specific_areas['Q'] = Polygon([(2, 7), (14, 7), (14, 9), (2, 9)])
    specific_areas['R'] = Polygon([(14, 7), (16, 7), (16, 9), (14, 9)])
    specific_areas['S'] = Polygon([(16, 7), (28, 7), (28, 9), (16, 9)])
    specific_areas['T'] = Polygon([(14, 9), (16, 9), (16, 14), (14, 14)])
    specific_areas['U'] = Polygon([(14, 2), (16, 2), (16, 7), (14, 7)])
    specific_areas['EA'] = Polygon([(14, 0), (14, -2), (16, -2), (16, 0)])
    specific_areas['EB'] = Polygon([(14, 16), (14, 18), (16, 18), (16, 16)])
    specific_areas['EC'] = Polygon([(30, 3.5), (32, 3.5), (32, 5.5), (30, 5.5)])
    specific_areas['ED'] = Polygon([(30, 10.5), (32, 10.5), (32, 12.5), (30, 12.5)])

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