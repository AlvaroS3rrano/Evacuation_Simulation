class SimulationConfig:
    """
    A class representing configuration parameters for a simulation.

    Attributes:
        simulation (any): An object or value representing the simulation.
        every_nth_frame (int): The frequency (every nth frame) at which simulation steps are processed.
        waypoints_ids (dict): A dictionary mapping graph node IDs to simulation waypoint IDs.
        journeys_ids (dict): A dictionary mapping journey identifiers (str) to a tuple (journey_id, path).
                             - journey_id: An identifier for the journey.
                             - path: The path associated with the journey.
        exit_ids (dict): A dictionary of exit IDs representing nodes where the simulation might terminate or transition.
    """

    def __init__(self, simulation=None, every_nth_frame_simulation=4, every_nth_frame_animation= 50, waypoints_ids=None, exit_ids=None):
        """
        Initializes the SimulationConfig with provided or default values.

        Args:
            simulation (any): The simulation object or identifier. Default is None.
            every_nth_frame (int): The frequency for processing simulation frames (must be a positive integer; default is 1).
            waypoints_ids (dict): A dictionary mapping node IDs to simulation waypoint IDs (default is an empty dictionary).
            journeys_ids (dict): A dictionary mapping journey identifiers to a tuple (journey_id, path).
                                 Default is an empty dictionary.
            exit_ids (dict): A dictionary of exit IDs. Default is an empty dictionary.
        """
        self.simulation = simulation
        self.every_nth_frame_simulation = every_nth_frame_simulation  # Uses the setter for validation.
        self.every_nth_frame_animation = every_nth_frame_animation  # Uses the setter for validation.
        self.waypoints_ids = waypoints_ids if waypoints_ids is not None else {}
        self.exit_ids = exit_ids if exit_ids is not None else {}

    def get_exit_ids_keys(self):
        """
        Returns the keys of the exit_ids dictionary.

        Returns:
            list: A list of keys present in exit_ids.
        """
        return list(self.exit_ids.keys())

    def __str__(self):
        """
        Returns a string representation of the simulation configuration.
        """
        return (f"SimulationConfig(simulation={self.simulation}, "
                f"every_nth_frame={self.every_nth_frame}, "
                f"waypoints_ids={self.waypoints_ids}, "
                f"exit_ids={self.exit_ids})")


# Example usage:
if __name__ == "__main__":

    # Initialize exit_ids as a dictionary, e.g., mapping exit names to node identifiers
    example_exit_ids = {
        "exitA": "Node_A",
        "exitB": "Node_B"
    }

    config = SimulationConfig(simulation="MySimulation", every_nth_frame=5,
                              waypoints_ids={"A": 101, "B": 102},
                              exit_ids=example_exit_ids)
    print(config)
    print("Exit IDs keys:", config.get_exit_ids_keys())
