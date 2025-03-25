class AgentGroup:
    """
    Represents a group of agents along with their designated path, the identifier of the algorithm used,
    the agents' awareness level, and information about the current floor.

    Attributes:
        agents (list): List of agent IDs.
        path (list): The designated path for the group in the global environment (across all floors).
        floor_path (list): The designated path for the group on the current floor.
        current_nodes (dict): Dictionary mapping each agent's ID to its current node.
        algorithm (int): Identifier for the algorithm used:
                         0: shortest path.
                         1: centrality measures.
        awareness_level (int): The agents' awareness level:
                               0: Only become aware upon reaching a neighboring node.
                               1: Become aware of every change in real time.
        blocked_nodes (list): List of nodes that are currently blocked.
        wait_until_node (str, optional): Node where agents wait before executing certain operations.
        areInStairs (list): List of agent IDs that are currently in a stairs node.
        current_floor (int or str): Identifier of the current floor where the group is located.
    """

    def __init__(self, agents, path, floor_path, current_nodes, algorithm, awareness_level, current_floor, *, blocked_nodes=None, wait_until_node=None, areInStairs=[]):
        """
        Initializes an AgentGroup instance.

        Parameters:
            agents (list): List of agent IDs.
            path (list): The designated path for the group in the global environment (across all floors).
            floor_path (list): The designated path for the group on the current floor.
            current_nodes (dict): Dictionary mapping each agent's ID to its current node.
            algorithm (int): Identifier for the algorithm to be used (0 for shortest path, 1 for centrality).
            awareness_level (int): The awareness level of the agents (0 or 1).
            current_floor (int or str): Identifier for the current floor where the group is located.
            blocked_nodes (list, optional): List of nodes that are initially blocked. Defaults to an empty list.
            wait_until_node (str, optional): The node at which the agents wait before executing certain operations.
            areInStairs (list, optional): List of agent IDs that are currently in stairs.
        """
        self.agents = agents
        self.path = path
        self.floor_path = floor_path
        self.current_nodes = current_nodes
        self.algorithm = algorithm
        self.awareness_level = awareness_level
        self.blocked_nodes = blocked_nodes if blocked_nodes is not None else []
        self.wait_until_node = wait_until_node
        self.areInStairs = areInStairs
        self.current_floor = current_floor

    def __repr__(self):
        """
        Returns a string representation of the AgentGroup instance for debugging purposes.
        """
        return (f"AgentGroup(agents={self.agents}, path={self.path}, "
                f"algorithm={self.algorithm}, awareness_level={self.awareness_level}, "
                f"current_floor={self.current_floor})")
