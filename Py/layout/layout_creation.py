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
mode = 4
fr = 11 + pl
sr = 13 + pl
c1 = 25
c2 = 26

distribution_polygons = {
'1': Polygon([(3.0, 0.0), (1.5, 0.0), (1.5, 1.0), (3.0, 1.0)]),
'2': Polygon([(1.5, 0.0), (0.0, 0.0), (0.0, 1.0), (1.5, 1.0)]),
'3': Polygon([(1.5, 1.0), (0.0, 1.0), (0.0, 2.0), (1.5, 2.0)]),
'4': Polygon([(3.0, 1.0), (1.5, 1.0), (1.5, 2.0), (3.0, 2.0)]),
'5': Polygon([(3.0, 0.0), (3.0, 2.0), (6.0, 2.0), (6.0, 0.0)]),
'6': Polygon([(3.0, 2.0), (3.0, 5.0), (6.0, 5.0), (6.0, 2.0)]),
'7': Polygon([(6.0, 2.0), (6.0, 5.0), (9.0, 5.0), (9.0, 2.0)]),
'8': Polygon([(9.0, 2.0), (9.0, 5.0), (12.0, 5.0), (12.0, 2.0)]),
'9': Polygon([(12.0, 2.0), (12.0, 3.0), (14.0, 3.0), (14.0, 2.0)]),
'10': Polygon([(14.0, 0.0), (14.0, 3.0), (17.0, 3.0), (17.0, 0.0)]),
'11': Polygon([(15.0, 3.0), (15.0, 5.0), (17.0, 5.0), (17.0, 3.0)]),
'12': Polygon([(17.0, 0.0), (18.5, 0.0), (18.5, 1.0), (17.0, 1.0)]),
'13': Polygon([(18.5, 0.0), (20.0, 0.0), (20.0, 1.0), (18.5, 1.0)]),
'14': Polygon([(18.5, 1.0), (20.0, 1.0), (20.0, 2.0), (18.5, 2.0)]),
'15': Polygon([(17.0, 1.0), (18.5, 1.0), (18.5, 2.0), (17.0, 2.0)]),
'16': Polygon([(3.0, 5.0), (3.0, 8.0), (4.0, 8.0), (4.0, 5.0)]),
'17': Polygon([(3.0, 8.0), (4.0, 8.0), (4.0, 11.0), (3.0, 11.0)]),
'18': Polygon([(3.0, 11.0), (4.0, 11.0), (4.0, 14.0), (3.0, 14.0)]),
'19': Polygon([(3.0, 14.0), (4.0, 14.0), (4.0, 17.0), (3.0, 17.0)]),
'20': Polygon([(3.0, 17.0), (4.0, 17.0), (4.0, 20.0), (3.0, 20.0)]),
'21': Polygon([(3.0, 20.0), (4.0, 20.0), (4.0, 23.0), (3.0, 23.0)]),
'22': Polygon([(3.0, 23.0), (4.0, 23.0), (4.0, 27.0), (3.0, 27.0)]),
'23': Polygon([(3.0, 27.0), (4.0, 27.0), (4.0, 30.0), (3.0, 30.0)]),
'24': Polygon([(9.0, 5.0), (9.0, 6.0), (12.0, 6.0), (12.0, 5.0)]),
'25': Polygon([(12.0, 5.0), (12.0, 6.0), (15.0, 6.0), (15.0, 5.0)]),
'26': Polygon([(15.0, 5.0), (15.0, 6.0), (17.0, 6.0), (17.0, 5.0)]),
'27': Polygon([(9.0, 6.0), (9.0, 9.0), (11.0, 9.0), (11.0, 6.0)]),
'28': Polygon([(9.0, 9.0), (11.0, 9.0), (11.0, 12.0), (9.0, 12.0)]),
'29': Polygon([(9.0, 12.0), (11.0, 12.0), (11.0, 15.0), (9.0, 15.0)]),
'30': Polygon([(9.0, 15.0), (11.0, 15.0), (11.0, 18.0), (9.0, 18.0)]),
'31': Polygon([(9.0, 18.0), (11.0, 18.0), (11.0, 21.0), (9.0, 21.0)]),
'32': Polygon([(9.0, 21.0), (11.0, 21.0), (11.0, 24.0), (9.0, 24.0)]),
'33': Polygon([(9.0, 24.0), (11.0, 24.0), (11.0, 26.0), (9.0, 26.0)]),
'34': Polygon([(16.0, 6.0), (17.0, 6.0), (17.0, 9.0), (16.0, 9.0)]),
'35': Polygon([(16.0, 9.0), (17.0, 9.0), (17.0, 12.0), (16.0, 12.0)]),
'36': Polygon([(16.0, 12.0), (17.0, 12.0), (17.0, 15.0), (16.0, 15.0)]),
'37': Polygon([(16.0, 15.0), (17.0, 15.0), (17.0, 18.0), (16.0, 18.0)]),
'38': Polygon([(16.0, 18.0), (17.0, 18.0), (17.0, 21.0), (16.0, 21.0)]),
'39': Polygon([(16.0, 21.0), (17.0, 21.0), (17.0, 25.0), (16.0, 25.0)]),
'40': Polygon([(4.0, 13.0), (6.5, 13.0), (6.5, 14.0), (4.0, 14.0)]),
'41': Polygon([(6.5, 13.0), (9.0, 13.0), (9.0, 14.0), (6.5, 14.0)]),
'42': Polygon([(4.0, 19.0), (6.5, 19.0), (6.5, 20.0), (4.0, 20.0)]),
'43': Polygon([(6.5, 19.0), (9.0, 19.0), (9.0, 20.0), (6.5, 20.0)]),
'44': Polygon([(4.0, 26.0), (7.0, 26.0), (7.0, 27.0), (4.0, 27.0)]),
'45': Polygon([(7.0, 26.0), (10.0, 26.0), (10.0, 28.0), (7.0, 28.0)]),
'46': Polygon([(4.0, 28.0), (7.0, 28.0), (7.0, 30.0), (4.0, 30.0)]),
'47': Polygon([(7.0, 28.0), (10.0, 28.0), (10.0, 29.0), (7.0, 29.0)]),
'48': Polygon([(10.0, 28.0), (13.0, 28.0), (13.0, 29.0), (10.0, 29.0)]),
'49': Polygon([(13.0, 28.0), (15.0, 28.0), (15.0, 29.0), (13.0, 29.0)]),
'50': Polygon([(15.0, 28.0), (17.0, 28.0), (17.0, 29.0), (15.0, 29.0)]),
'51': Polygon([(17.0, 28.0), (19.0, 28.0), (19.0, 29.0), (17.0, 29.0)]),
'52': Polygon([(11.0, 25.0), (13.0, 25.0), (13.0, 26.0), (11.0, 26.0)]),
'53': Polygon([(13.0, 25.0), (15.0, 25.0), (15.0, 26.0), (13.0, 26.0)]),
'54': Polygon([(15.0, 25.0), (17.0, 25.0), (17.0, 26.0), (15.0, 26.0)]),
'55': Polygon([(17.0, 25.0), (19.0, 25.0), (19.0, 26.0), (17.0, 26.0)]),
'56': Polygon([(13.0, 26.0), (15.0, 26.0), (15.0, 28.0), (13.0, 28.0)]),
'57': Polygon([(18.0, 26.0), (19.0, 26.0), (19.0, 28.0), (18.0, 28.0)]),
'58': Polygon([(11.0, 15.0), (13.5, 15.0), (13.5, 16.0), (11.0, 16.0)]),
'59': Polygon([(13.5, 15.0), (16.0, 15.0), (16.0, 16.0), (13.5, 16.0)]),

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
