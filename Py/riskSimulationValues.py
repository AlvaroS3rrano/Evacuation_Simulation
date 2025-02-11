class RiskSimulationValues:
    """
    A class representing the parameters for a risk simulation.
    """

    def __init__(self, iterations=10000, propagation_chance=0.003, increase_chance=0.01):
        """
        Initializes the RiskSimulationValues class with default or provided values.

        :param iterations: Total number of frames for the simulation (default is 10000).
        :param propagation_chance: Probability of risk propagation between nodes (default is 0.003).
        :param increase_chance: Probability of individual risk increase (default is 0.01).
        """
        self._iterations = iterations  # Total number of frames for the simulation
        self._propagation_chance = propagation_chance  # Probability of risk propagation between nodes
        self._increase_chance = increase_chance  # Probability of individual risk increase

    # Getter and Setter for iterations
    @property
    def iterations(self):
        """
        Gets the total number of simulation iterations.
        """
        return self._iterations

    @iterations.setter
    def iterations(self, value):
        """
        Sets the total number of simulation iterations.
        Ensures the value is a positive integer.

        :param value: The new number of iterations.
        :raises ValueError: If value is not a positive integer.
        """
        if isinstance(value, int) and value > 0:
            self._iterations = value
        else:
            raise ValueError("iterations must be a positive integer.")

    # Getter and Setter for propagation_chance
    @property
    def propagation_chance(self):
        """
        Gets the probability of risk propagation between nodes.
        """
        return self._propagation_chance

    @propagation_chance.setter
    def propagation_chance(self, value):
        """
        Sets the probability of risk propagation between nodes.
        Ensures the value is between 0 and 1.

        :param value: The new propagation probability.
        :raises ValueError: If value is not between 0 and 1.
        """
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            self._propagation_chance = value
        else:
            raise ValueError("propagation_chance must be between 0 and 1.")

    # Getter and Setter for increase_chance
    @property
    def increase_chance(self):
        """
        Gets the probability of individual risk increase.
        """
        return self._increase_chance

    @increase_chance.setter
    def increase_chance(self, value):
        """
        Sets the probability of individual risk increase.
        Ensures the value is between 0 and 1.

        :param value: The new increase probability.
        :raises ValueError: If value is not between 0 and 1.
        """
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            self._increase_chance = value
        else:
            raise ValueError("increase_chance must be between 0 and 1.")

    def __str__(self):
        """
        Returns a string representation of the simulation parameters.
        """
        return (f"RiskSimulationValues(iterations={self._iterations}, "
                f"propagation_chance={self._propagation_chance}, "
                f"increase_chance={self._increase_chance})")


# Example usage:
simulation = RiskSimulationValues()
print(simulation)  # Displays the default values