class AgentGroup:
    """
    Represents a group of agents along with their designated path, algorithm identifier, and knowledge level.

    Attributes:
        agents (list): List of agent IDs.
        path (list): The designated path for the agent group (as a list of nodes).
        current_nodes (dict): Dictionary mapping each agent's ID to the current node where the agent is located.
        algorithm (int): Identifier for the algorithm used:
                         0: shortest path
                         1: centrality measures
        awareness_level (int): The awareness level of the agents:
                               0: Knows only upon reaching a neighboring node.
                               1: Knows every change as it happens.
        blocked_nodes (list): List of nodes that are currently blocked.
    """

    def __init__(self, agents, path, current_nodes, algorithm, awareness_level, *, blocked_nodes=None, wait_until_node=None, areInStairs=[]):
        """
        Initializes an AgentGroup instance.

        Parameters:
            agents (list): List of agent IDs.
            path (list): The designated path for the group.
            current_nodes (dict): Dictionary mapping each agent's ID to its current node.
            algorithm (int): Algorithm identifier (e.g., 0 for shortest path, 1 for centrality measures).
            awareness_level (int): The awareness level of the agents (e.g., 0 or 1).
            blocked_nodes (list, optional): List of nodes to mark as blocked initially.
                                            Defaults to an empty list if not provided.
            wait_until_node (str, optional): Node identifier to wait at before executing certain operations.
                                             The related function will only execute once the agent reaches this node.
        """
        self.agents = agents                          # List of agent IDs.
        self.path = path                              # Designated path for the group.
        self.current_nodes = current_nodes            # Dictionary mapping agent IDs to their current nodes.
        self.algorithm = algorithm                    # Algorithm used (0 for shortest path, 1 for centrality measures).
        self.awareness_level = awareness_level        # Awareness level (0 or 1).
        self.blocked_nodes = blocked_nodes if blocked_nodes is not None else []
        self.wait_until_node = wait_until_node        # Node at which to continue looking for new paths
        self.areInStairs = areInStairs                # List of agents IDs that are in a stairs node

    def __repr__(self):
        """
        Returns a string representation of the AgentGroup instance, useful for debugging.
        """
        return (f"AgentGroup(agents={self.agents}, path={self.path}, "
                f"algorithm={self.algorithm}, awareness_level={self.awareness_level})")
