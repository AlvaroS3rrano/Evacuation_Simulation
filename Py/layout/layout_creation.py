from shapely.geometry import Polygon
import math

def transform_dictionary(input_data):
    """
    Receives a dictionary where each value is a Polygon object.
    Returns a new dictionary where each key is associated with a tuple:
    ([x_center, y_center], 1.5)
    """
    output_data = {}
    for key, polygon in input_data.items():
        center = polygon.centroid
        output_data[key] = ([center.x, center.y], 0.5)
    return output_data


def polygon_to_string(polygon):
    """
    Receives a Polygon object and returns a string with the format:
    "Polygon([(x1, y1), (x2, y2), ..., (xn, yn)])"
    The last point is omitted if it is equal to the first, since in the original input it is not repeated.
    """
    # Extract the coordinates of the exterior boundary
    coords = list(polygon.exterior.coords)
    # If the polygon is closed (the first point is repeated at the end), remove the last one
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    # Format each tuple as (x, y)
    formatted_coords = ", ".join(f"({x}, {y})" for x, y in coords)
    return f"Polygon([{formatted_coords}])"


def renumber_dictionary(input_data):
    """
    Receives a dictionary with keys in string format and Polygon values.
    Returns a new dictionary with keys renumbered sequentially (as strings)
    while preserving the original format.
    """
    output_data = {}
    for i, (_, value) in enumerate(input_data.items(), start=1):
        output_data[str(i)] = value
    return output_data


def generate_edges(polygons_dict):
    """
    Generates a list of edges for a digraph.
    Two nodes are considered connected (and an edge is generated in both directions)
    if their areas (polygons) touch.

    Parameters:
        polygons_dict (dict): Dictionary with keys (str) and Polygon values.

    Returns:
        list: List of tuples (source, destination) representing the edges.
    """
    edges = []
    # Convert the dictionary to a list of (id, polygon) to iterate over all pairs
    nodes = list(polygons_dict.items())

    # Iterate over each pair of nodes
    for i, (id1, poly1) in enumerate(nodes):
        for j, (id2, poly2) in enumerate(nodes):
            if id1 != id2:
                # If the areas touch, they are considered connected
                if poly1.touches(poly2):
                    edges.append((id1, id2))
    return edges


def generate_zero_values(dictionary):
    """
    Receives a dictionary and returns another where each key
    is associated with the value 0.0.

    Example:
        Input: {"A": <value>, "B": <value>, ...}
        Output: {"A": 0.0, "B": 0.0, ...}
    """
    return {key: 0.0 for key in dictionary.keys()}

def compute_distance(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def get_edge_costs_from_waypoints(waypoints, edges):
    costs = []
    for start, end in edges:
        start_coords = waypoints[start][0]
        end_coords = waypoints[end][0]
        distance = compute_distance(start_coords, end_coords)
        costs.append((start, end, distance))
    return costs

# '53': Polygon([(11, 25), (13, 25), (13, 26), (11, 26)]),
n = 13
pl = 5
mode = 6
fr = 0 + pl
sr = 5 + pl
c1 = 0
c2 = 5

distribution_polygons = {
      '1': Polygon([[0,0],[5,0],[5,5],[0,5]]),
    '2': Polygon([(5, 0), (10, 0), (10, 5), (5, 5)]),
    '3': Polygon([(10, 0), (15, 0), (15, 5), (10, 5)]),
    '4': Polygon([(15, 0), (20, 0), (20, 5), (15, 5)]),
    '5': Polygon([(20, 0), (25, 0), (25, 5), (20, 5)]),
    '6': Polygon([(25, 0), (30, 0), (30, 5), (25, 5)]),
    '7': Polygon([(30, 0), (35, 0), (35, 5), (30, 5)]),
    '8': Polygon([(35, 0), (40, 0), (40, 5), (35, 5)]),
    '9': Polygon([(40, 0), (45, 0), (45, 5), (40, 5)]),
    '10': Polygon([(45, 0), (50, 0), (50, 5), (45, 5)]),
    '11': Polygon([(50, 0), (55, 0), (55, 5), (50, 5)]),
    '12': Polygon([(55, 0), (60, 0), (60, 5), (55, 5)]),
    '13': Polygon([(60, 0), (65, 0), (65, 5), (60, 5)]),
    '14': Polygon([(65, 0), (70, 0), (70, 5), (65, 5)]),
'15': Polygon([[50,5], [55,5], [55,10], [50,10]]),
    '16': Polygon([[40,-5], [45,-5], [45,0], [40,0]])

}

waypoints = {
    '1': ([10, 13], 1.5),
    '2': ([15.0, 13.0], 0.9),
    '3': ([15.0, 16.0], 1.8),
    '4': ([18.5, 16.0], 1.5),
    '5': ([18.5, 13.0], 0.75),
    '6': ([21.0, 16.0], 0.65),
    '7': ([23.0, 16.0], 0.65),
    '8': ([23.0, 13.0], 0.65),
    '9': ([21.666666666666668, 8.833333333333334], 2.4),
    '10': ([26.0, 7.5], 1.4),
    '11': ([25.09090909090909, 10.5], 0.85),
    '12': ([25.0, 12.75], 0.5),
    '13': ([25.0, 15.6], 0.70),
    '14': ([29.25, 17.0], 2.8),
    '15': ([28.0, 13.0], 0.75),
    '16': ([30.74912985274431, 12.70548862115127], 0.75),
    '17': ([34.53260869565217, 17.347826086956523], 2.0),
    '18': ([34.75, 21.0], 0.70),
    '19': ([38.0, 21.0], 0.65),
    '20': ([28.25, 21.0], 0.70),
    '21': ([34.75, 25.0], 2.1),
    '22': ([29.25, 25.0], 2.7),
    '23': ([31.5, 30.25], 2.1),
    '24': ([26.5, 29.0], 0.65),
    '25': ([25.0, 25.5], 0.65),
    '26': ([25.0, 20.6], 0.70),
    '27': ([22.0, 20.0], 1.7),
    '28': ([23.0, 25.5], 0.65),
    '29': ([20.90909090909091, 29.522727272727273], 1.7),
    '30': ([23.5, 32.5], 1.0),
    '31': ([26.72222222222222, 30.944444444444443], 0.75),
    '32': ([21.0, 24.25], 0.70),
    '33': ([19.0, 24.25], 0.70),
    '34': ([19.0, 20.0], 0.65),
    '35': ([15.5, 21.25], 2.4),
    '36': ([15.5, 26.0], 1.4),
    '37': ([15.0, 29.25], 1.5),
    '38': ([11.5, 26.0], 1.0),
    '39': ([8.416666666666666, 26.791666666666668], 0.85),
    '40': ([11.5, 22.25], 0.75),
    '41': ([11.566666666666666, 17.166666666666668], 1.0),
    '42': ([7.568965517241379, 20.810344827586206], 2.0),
}

edges = [
('1', '2'),
        ('2', '1'),
        ('2', '3'),
        ('3', '2'),
        ('3', '4'),
        ('3', '35'),
        ('3', '41'),
        ('4', '3'),
        ('4', '5'),
        ('4', '6'),
        ('4', '34'),
        ('5', '4'),
        ('6', '4'),
        ('6', '7'),
        ('6', '27'),
        ('7', '6'),
        ('7', '8'),
        ('7', '13'),
        ('8', '7'),
        ('8', '9'),
        ('9', '8'),
        ('9', '10'),
        ('9', '11'),
        ('10', '9'),
        ('11', '9'),
        ('11', '12'),
        ('12', '11'),
        ('12', '13'),
        ('13', '7'),
        ('13', '12'),
        ('13', '14'),
        ('13', '26'),
        ('14', '13'),
        ('14', '15'),
        ('14', '16'),
        ('14', '17'),
        ('14', '20'),
        ('15', '14'),
        ('16', '14'),
        ('17', '14'),
        ('17', '18'),
        ('18', '17'),
        ('18', '19'),
        ('18', '20'),
        ('18', '21'),
        ('19', '18'),
        ('20', '14'),
        ('20', '18'),
        ('20', '22'),
        ('20', '26'),
        ('21', '18'),
        ('21', '22'),
        ('22', '20'),
        ('22', '21'),
        ('22', '23'),
        ('23', '22'),
        ('23', '24'),
        ('24', '23'),
        ('24', '25'),
        ('25', '24'),
        ('25', '26'),
        ('25', '28'),
        ('26', '13'),
        ('26', '20'),
        ('26', '25'),
        ('26', '27'),
        ('27', '6'),
        ('27', '26'),
        ('27', '28'),
        ('27', '32'),
        ('28', '25'),
        ('28', '27'),
        ('28', '29'),
        ('29', '28'),
        ('29', '30'),
        ('29', '31'),
        ('29', '32'),
        ('29', '37'),
        ('30', '29'),
        ('30', '31'),
        ('31', '29'),
        ('31', '30'),
        ('32', '27'),
        ('32', '29'),
        ('32', '33'),
        ('33', '32'),
        ('33', '34'),
        ('33', '36'),
        ('34', '4'),
        ('34', '33'),
        ('34', '35'),
        ('35', '3'),
        ('35', '34'),
        ('35', '36'),
        ('36', '33'),
        ('36', '35'),
        ('36', '37'),
        ('36', '38'),
        ('37', '29'),
        ('37', '36'),
        ('38', '36'),
        ('38', '39'),
        ('38', '40'),
        ('39', '38'),
        ('40', '38'),
        ('40', '41'),
        ('41', '3'),
        ('41', '40'),
        ('41', '42'),
        ('42', '41'),
]
if mode == 0:  # vertical
    for i in range(n):
        print(f"'{1+i}': Polygon([({c1},{fr}), ({c2}, {fr}), ({c2}, {sr}), ({c1}, {sr})]),")
        fr += pl
        sr += pl
elif mode == 1:  # horizontal
    for i in range(n):
        print(f"'{2+i}': Polygon([({fr}, {c1}), ({sr}, {c1}), ({sr}, {c2}), ({fr}, {c2})]),")
        fr += pl
        sr += pl
elif mode == 2:
    result = transform_dictionary(distribution_polygons)
    for key, value in result.items():
        print(f"'{key}': {value},")
elif mode == 3:
    renumbered_dictionary = renumber_dictionary(distribution_polygons)
    # Print the renumbered dictionary
    for key, polygon in renumbered_dictionary.items():
        print(f"'{key}': {polygon_to_string(polygon)},")
elif mode == 4:
    edges = generate_edges(distribution_polygons)
    print("edges = [")
    for edge in edges:
        print(f"    {edge},")
    print("]")
elif mode == 5:
    zero_values = generate_zero_values(distribution_polygons)
    # Print in the desired format
    for key, value in zero_values.items():
        print(f'"{key}": {value},')
elif mode == 6:
    costs = get_edge_costs_from_waypoints(waypoints, edges)
    for cost in costs:
        print(cost)