class RiskSimulationValues:
    """
    Represents the configuration parameters for a risk simulation.

    Attributes:
        iterations (int): Total number of simulation frames.
        increase_chance (float): Probability of an individual risk increase per frame.
        danger_threshold (float): Risk value above which a node is considered dangerous.
        risk_overrides (list of tuple, optional): Optional list of (frame, node, risk)
            tuples to force-set specific node risks at given frames. Defaults to an empty list.
        starting_risks (list of tuple, optional): Optional list of (node, risk)
            tuples to define the initial risk values of specific nodes. Defaults to an empty list.
    """

    def __init__(
        self,
        iterations: int = 3000,
        increase_chance: float = 0.01,
        danger_threshold: float = 0.5,
        starting_risks: list[tuple[str, float]] | None = None,
        risk_overrides: list[tuple[int, str, float]] | None = None,
    ):
        """
        Initializes a RiskSimulationValues instance with provided or default parameters.

        Parameters:
            iterations (int): Total number of simulation frames (default is 3000).
            increase_chance (float): Probability of an individual risk increase per frame (default is 0.01).
            danger_threshold (float): Risk threshold to define a dangerous node (default is 0.5).
            starting_risks (list of (str, float) tuples, optional):
                Defines initial risk values for specific nodes (default is None → empty list).
            risk_overrides (list of (int, str, float) tuples, optional):
                Forcibly sets node risk at specific frames (default is None → empty list).
        """
        self.iterations = iterations
        self.increase_chance = increase_chance
        self.danger_threshold = danger_threshold
        self.starting_risks = starting_risks or []
        self.risk_overrides = risk_overrides or []

if __name__ == "__main__":

    # Example usage:
    simulation = RiskSimulationValues()
    print(simulation)  # Displays the default values