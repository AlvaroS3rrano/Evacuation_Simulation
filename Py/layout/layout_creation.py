import math
from shapely.geometry import Polygon

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

from shapely.geometry import Polygon

def split_and_format(polygon, n):
    """
    Splits a horizontal rectangular polygon into `n` parts and prints them in your desired format.
    """
    minx, miny, maxx, maxy = polygon.bounds
    total_width = maxx - minx
    segment_width = total_width / n
    segments = {}

    for i in range(n):
        x1 = round(minx + i * segment_width, 4)
        x2 = round(x1 + segment_width, 4)
        new_poly = Polygon([
            (x1, miny), (x1, maxy),
            (x2, maxy), (x2, miny)
        ])
        segments[str(i + 1)] = new_poly

    # Print in desired format
    for key, poly in segments.items():
        coords = ", ".join([f"({round(x, 4)}, {round(y, 4)})" for x, y in poly.exterior.coords[:-1]])  # skip closing point
        print(f"'{key}': Polygon([{coords}]),")

def split_vertically(polygon, n):
    """
    Splits a rectangular polygon vertically into `n` parts (preserving width).
    """
    minx, miny, maxx, maxy = polygon.bounds
    total_height = maxy - miny
    segment_height = total_height / n
    segments = {}

    for i in range(n):
        y1 = round(miny + i * segment_height, 4)
        y2 = round(y1 + segment_height, 4)
        new_poly = Polygon([
            (minx, y1), (minx, y2),
            (maxx, y2), (maxx, y1)
        ])
        segments[str(i + 1)] = new_poly

    for key, poly in segments.items():
        coords = ", ".join([f"({round(x, 4)}, {round(y, 4)})" for x, y in poly.exterior.coords[:-1]])
        print(f"'{key}': Polygon([{coords}]),")

# '53': Polygon([(11, 25), (13, 25), (13, 26), (11, 26)]),
n = 2
pl = 5
mode = 6
fr = 0 + pl
sr = 5 + pl
c1 = 0
c2 = 5

distribution_polygons = {
'1': Polygon([(24.0, 14.0), (24.0, 16.0), (26.0, 16.0), (26.0, 14.0)]),
'2': Polygon([(24.0, 16.0), (24.0, 18.0), (26.0, 18.0), (26.0, 16.0)]),

}

waypoints = {
        '1': ([10, 13], 1.5),
        '2': ([15.0, 13.0], 0.9),
        '3': ([15.0, 16.0], 1.8),
        '4': ([18.5, 16.0], 1.5),
        '5': ([18.5, 13.0], 0.75),
        '6': ([21.0, 15.0], 0.65),
        '7': ([23.0, 15.5], 0.85),
        '8': ([23.0, 13.0], 0.65),
        '9': ([21.666666666666668, 8.833333333333334], 2.4),
        '10': ([26.0, 7.5], 1.4),
        '11': ([25.09090909090909, 10.5], 0.85),
        '12': ([25.0, 12.75], 0.5),
        '13': ([25.0, 15.0], 0.7),
        '14': ([28.75, 15.5], 1.6),
        '15': ([31.25, 17.0], 1.0),
        '16': ([28.25, 19.0], 0.7),
        '17': ([28.0, 13.0], 0.7),
        '18': ([32.24912985274431, 12.70548862115127], 0.7),
        '19': ([34.53260869565217, 17.347826086956523], 0.8),
        '20': ([33.25, 21.0], 0.5),
        '21': ([34.75, 21.0], 0.85),
        '22': ([36.25, 21.0], 0.5),
        '23': ([38.0, 21.0], 0.7),
        '24': ([26.8125, 21.0], 0.5),
        '25': ([28.4375, 21.0], 0.7),
        '26': ([30.0625, 21.0], 0.5),
        '27': ([31.6875, 21.0], 0.5),
        '28': ([34.75, 23.0], 1.0),
        '29': ([34.75, 25.0], 1.0),
        '30': ([33.75, 27.0], 1.2),
        '31': ([28.25, 23.0], 1.0),
        '32': ([29.25, 25.0], 1.5),
        '33': ([31.25, 26.7], 1.0),
        '34': ([31.5, 29.125], 1.0),
        '35': ([31.5, 31.775], 1.0),
        '36': ([24.833349999999996, 29.0], 0.7),
        '37': ([26.50005, 28.999999999999996], 0.7),
        '38': ([28.166650000000004, 29.0], 0.7),
        '39': ([25.0, 23.833349999999996], 0.5),
        '40': ([24.999999999999996, 25.500049999999998], 0.5),
        '41': ([25.0, 27.16665], 0.5),
        '42': ([25.0, 18.83335], 0.5),
        '43': ([24.999999999999996, 20.50005], 0.7),
        '44': ([25.0, 22.166650000000004], 0.5),
        '45': ([22.0, 20.0], 1.5),
        '46': ([23.0, 23.0], 0.6),
        '47': ([23.0, 25.5], 0.6),
        '48': ([23.0, 28.0], 0.6),
        '49': ([20.90909090909091, 29.522727272727273], 2.0),
        '50': ([23.5, 32.5], 0.9),
        '51': ([26.72222222222222, 30.944444444444443], 0.6),
        '52': ([21.0, 22.91665], 0.6),
        '53': ([21.000000000000004, 24.249950000000002], 0.6),
        '54': ([21.0, 26.38335], 0.6),
        '55': ([19.0, 22.41665], 0.6),
        '56': ([18.999999999999996, 24.249950000000002], 0.6),
        '57': ([19.0, 26.08335], 0.6),
        '58': ([19.0, 20.0], 0.5),
        '59': ([15.5, 21.25], 2.5),
        '60': ([13.533349999999998, 25.999999999999996], 0.7),
        '61': ([15.80005, 26.], 1.0),
        '62': ([17.566650000000004, 26.000000000000004], 0.7),
        '63': ([15.0, 29.25], 1.5),
        '64': ([11.5, 26.0], 0.7),
        '65': ([8.916666666666666, 26.791666666666668], 1.0),
        '66': ([11.5, 21.125], 0.7),
        '67': ([11.5, 23.375], 0.7),
        '68': ([11.566666666666666, 17.166666666666668], 1.0),
        '69': ([7.568965517241379, 20.810344827586206], 1.5),
        '70': ([25.0, 17.0], 0.7),
    }

original_polygon = Polygon([(24.0, 14.0), (24.0, 18.0), (26.0, 18.0), (26.0, 14.0)])
edges = [
        ('1', '2'),
        ('2', '1'),
        ('2', '3'),
        ('3', '2'),
        ('3', '4'),
        ('3', '59'),
        ('3', '68'),
        ('4', '3'),
        ('4', '5'),
        ('4', '6'),
        ('4', '58'),
        ('5', '4'),
        ('6', '4'),
        ('6', '7'),
        ('6', '45'),
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
        ('13', '12'),
        ('13', '14'),
        ('13', '70'),
        ('14', '13'),
        ('14', '15'),
        ('14', '16'),
        ('14', '17'),
        ('14', '18'),
        ('15', '14'),
        ('15', '16'),
        ('15', '19'),
        ('16', '14'),
        ('16', '15'),
        ('16', '25'),
        ('17', '14'),
        ('18', '14'),
        ('19', '15'),
        ('19', '21'),
        ('19', '22'),
        ('20', '21'),
        ('20', '27'),
        ('21', '19'),
        ('21', '20'),
        ('21', '22'),
        ('21', '28'),
        ('22', '19'),
        ('22', '21'),
        ('22', '23'),
        ('23', '22'),
        ('24', '25'),
        ('24', '43'),
        ('25', '16'),
        ('25', '24'),
        ('25', '26'),
        ('25', '31'),
        ('26', '25'),
        ('26', '27'),
        ('27', '20'),
        ('27', '26'),
        ('28', '21'),
        ('28', '29'),
        ('29', '28'),
        ('29', '30'),
        ('30', '29'),
        ('30', '33'),
        ('31', '25'),
        ('31', '32'),
        ('32', '31'),
        ('32', '33'),
        ('33', '30'),
        ('33', '32'),
        ('33', '34'),
        ('34', '33'),
        ('34', '35'),
        ('34', '38'),
        ('35', '34'),
        ('36', '37'),
        ('36', '41'),
        ('37', '36'),
        ('37', '38'),
        ('38', '34'),
        ('38', '37'),
        ('39', '40'),
        ('39', '44'),
        ('40', '39'),
        ('40', '41'),
        ('40', '47'),
        ('41', '36'),
        ('41', '40'),
        ('42', '43'),
        ('42', '70'),
        ('43', '24'),
        ('43', '42'),
        ('43', '44'),
        ('43', '45'),
        ('44', '39'),
        ('44', '43'),
        ('45', '6'),
        ('45', '43'),
        ('45', '44'),
        ('45', '46'),
        ('45', '52'),
        ('46', '45'),
        ('46', '47'),
        ('47', '40'),
        ('47', '46'),
        ('47', '48'),
        ('48', '47'),
        ('48', '49'),
        ('49', '48'),
        ('49', '50'),
        ('49', '51'),
        ('49', '54'),
        ('49', '63'),
        ('50', '49'),
        ('50', '51'),
        ('51', '49'),
        ('51', '50'),
        ('52', '45'),
        ('52', '53'),
        ('53', '52'),
        ('53', '54'),
        ('53', '56'),
        ('54', '49'),
        ('54', '53'),
        ('55', '56'),
        ('55', '58'),
        ('56', '53'),
        ('56', '55'),
        ('56', '57'),
        ('57', '56'),
        ('57', '62'),
        ('58', '4'),
        ('58', '55'),
        ('58', '59'),
        ('59', '3'),
        ('59', '58'),
        ('59', '61'),
        ('60', '61'),
        ('60', '64'),
        ('61', '59'),
        ('61', '60'),
        ('61', '62'),
        ('61', '63'),
        ('62', '57'),
        ('62', '59'),
        ('62', '62'),
        ('62', '63'),
        ('63', '49'),
        ('63', '61'),
        ('64', '60'),
        ('64', '65'),
        ('64', '67'),
        ('65', '64'),
        ('66', '67'),
        ('66', '68'),
        ('67', '64'),
        ('67', '66'),
        ('68', '3'),
        ('68', '66'),
        ('68', '69'),
        ('69', '68'),
        ('70', '7'),
        ('70', '13'),
        ('70', '42'),
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
elif mode == 7:
    split_and_format(original_polygon, n)
elif mode == 8:
    split_vertically(original_polygon, n)