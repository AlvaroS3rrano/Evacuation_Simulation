class AgentGroup:
    """
    Represents a group of agents along with their designated path, algorithm identifier, and knowledge level.

    Attributes:
        agents (list): List of agent IDs.
        path (list): The designated path for the agent group (as a list of nodes).
        current_node (str): Identifier for the current node where the agent group is located.
        algorithm (int): Identifier for the algorithm used:
                         0: shortest path
                         1: centrality measures
        knowledge_level (int): The knowledge level of the agents:
                               0: Knows only upon reaching a neighboring node.
                               1: Knows every change as it happens.
        blocked_nodes (list): List of nodes that are currently blocked.
    """

    def __init__(self, agents, path, current_node, algorithm, knowledge_level, *, blocked_nodes=None, wait_until_node=None):
        """
        Initializes an AgentGroup instance.

        Parameters:
            agents (list): List of agent IDs.
            path (list): The designated path for the group.
            current_node (str): Identifier of the current node.
            algorithm (int): Algorithm identifier (e.g., 0 for shortest path, 1 for centrality measures).
            knowledge_level (int): The knowledge level of the agents (e.g., 0 or 1).
            blocked_nodes (list, optional): List of nodes to mark as blocked initially.
                                            Defaults to an empty list if not provided.
            wait_until_node (str, optional): Node identifier to wait at before executing certain operations.
                                             The related function will only execute once current_node matches wait_until_node.
        """
        self.agents = agents                          # List of agent IDs.
        self.path = path                              # Designated path for the group.
        self.current_node = current_node              # Identifier of the current node.
        self.algorithm = algorithm                    # Algorithm used (0 for shortest path, 1 for centrality measures).
        self.knowledge_level = knowledge_level        # Knowledge level (0 or 1).
        self.blocked_nodes = blocked_nodes if blocked_nodes is not None else []
        self.wait_until_node = wait_until_node        # Node at which to continue looking for new paths

    def __repr__(self):
        """
        Returns a string representation of the AgentGroup instance, useful for debugging.
        """
        return (f"AgentGroup(agents={self.agents}, path={self.path}, "
                f"algorithm={self.algorithm}, knowledge_level={self.knowledge_level})")