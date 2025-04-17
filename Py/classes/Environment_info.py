class Environment_info:

    def __init__(self, graph, paths_connection, *,floors=None, floor_number=1, floor_connecting_nodes={}):

        self.graph = graph
        self.floors = floors
        self.floor_number = floor_number
        self.floor_connecting_nodes = floor_connecting_nodes
        self.floor_paths = {}
        self.paths_connection = paths_connection
