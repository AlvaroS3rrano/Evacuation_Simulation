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


# '100': Polygon([(17.0, 25.0), (23.0, 25.0), (23.0, 29.0), (17.0, 29.0)]),
n = 20
pl = 4
mode = 5
fr = 25 + pl
sr = 29 + pl
c1 = 17
c2 = 23

distribution_polygons = {
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

if mode == 0:  # vertical
    for i in range(n):
        print(f"'{101+i}': Polygon([({c1},{fr}), ({c2}, {fr}), ({c2}, {sr}), ({c1}, {sr})]),")
        fr += pl
        sr += pl
elif mode == 1:  # horizontal
    for i in range(n):
        print(f"'{81+i}': Polygon([({fr}, {c1}), ({sr}, {c1}), ({sr}, {c2}), ({fr}, {c2})]),")
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
