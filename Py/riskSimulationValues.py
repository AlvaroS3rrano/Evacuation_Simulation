class RiskSimulationValues:
    """
    Represents the configuration parameters for a risk simulation.

    Attributes:
        iterations (int): Total number of simulation frames.
        increase_chance (float): Probability of an individual risk increase per frame.
        danger_threshold (float): Risk value above which a node is considered dangerous.
    """

    def __init__(self, iterations=3000, increase_chance=0.01, danger_threshold=0.5):
        """
        Initializes a RiskSimulationValues instance with provided or default parameters.

        Parameters:
            iterations (int): Total number of simulation frames (default is 3000).
            increase_chance (float): Probability of an individual risk increase per frame (default is 0.01).
            danger_threshold (float): Risk threshold to define a dangerous node (default is 0.5).
        """
        self.iterations = iterations           # Total number of simulation frames.
        self.increase_chance = increase_chance   # Probability of an individual risk increase per frame.
        self.danger_threshold = danger_threshold  # Threshold value for considering a node dangerous.



if __name__ == "__main__":

    # Example usage:
    simulation = RiskSimulationValues()
    print(simulation)  # Displays the default values