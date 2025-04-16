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


# '53': Polygon([(11, 25), (13, 25), (13, 26), (11, 26)]),
n = 10
pl = 2
mode = 2
fr = 11 + pl
sr = 13 + pl
c1 = 25
c2 = 26

distribution_polygons = {
'91': Polygon([(11.0, 25.0), (18.0, 25.0), (18.0, 29.0), (11.0, 29.0)]),
        '92': Polygon([(11.0, 29.0), (18.0, 29.0), (18.0, 33.0), (11.0, 33.0)]),
        '93': Polygon([(11.0, 33.0), (18.0, 33.0), (18.0, 37.0), (11.0, 37.0)]),
        '94': Polygon([(11.0, 37.0), (18.0, 37.0), (18.0, 41.0), (11.0, 41.0)]),
        '95': Polygon([(18.0, 25.0), (23.0, 25.0), (23.0, 29.0), (18.0, 29.0)]),
        '96': Polygon([(18.0, 29.0), (23.0, 29.0), (23.0, 33.0), (18.0, 33.0)]),
        '97': Polygon([(18.0, 33.0), (23.0, 33.0), (23.0, 37.0), (18.0, 37.0)]),
        '98': Polygon([(18.0, 37.0), (23.0, 37.0), (23.0, 41.0), (18.0, 41.0)]),

}

if mode == 0:  # vertical
    for i in range(n):
        print(f"'{35+i}': Polygon([({c1},{fr}), ({c2}, {fr}), ({c2}, {sr}), ({c1}, {sr})]),")
        fr += pl
        sr += pl
elif mode == 1:  # horizontal
    for i in range(n):
        print(f"'{54+i}': Polygon([({fr}, {c1}), ({sr}, {c1}), ({sr}, {c2}), ({fr}, {c2})]),")
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