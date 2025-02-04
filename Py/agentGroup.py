class AgentGroup:
    """
    Represents a group of agents along with a designated path, algorithm identifier, and knowledge level.

    Attributes:
        agents (list): List of agent IDs.
        path (list): List representing the group's path.
        algorithm (int): Identifier for the algorithm used:
            - 0: shortest path
            - 1: centrality measures
        knowledge_level (int): The knowledge level of the agents:
            - 0: Knows only when reaching the neighboring node
            - 1: Knows every change as it happens
    """
    def __init__(self, agents, path, algorithm, knowledge_level):
        self.agents = agents            # List of agent IDs.
        self.path = path                # List representing the group's path.
        self.algorithm = algorithm      # Integer representing the algorithm.
        self.knowledge_level = knowledge_level  # Integer representing the knowledge level.

    def __repr__(self):
        return (f"AgentGroup(agents={self.agents}, path={self.path}, "
                f"algorithm={self.algorithm}, knowledge_level={self.knowledge_level})")
