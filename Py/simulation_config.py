class SimulationConfig:
    """
    A class representing configuration parameters for a simulation.

    Attributes:
        simulation (any): An object or value representing the simulation.
        every_nth_frame (int): The frequency (every nth frame) at which simulation steps are processed.
        waypoints_ids (dict): A dictionary mapping graph node IDs to simulation waypoint IDs.
        journeys_ids (dict): A dictionary mapping journey identifiers (str) to a tuple (journey_id, path).
                             - journey_id: an identifier for the journey.
                             - path: the path associated with the journey.
    """

    def __init__(self, simulation=None, every_nth_frame=1, waypoints_ids=None, journeys_ids=None):
        """
        Initializes the SimulationConfig with provided or default values.

        Args:
            simulation (any): The simulation object or identifier. Default is None.
            every_nth_frame (int): The frequency for processing simulation frames (must be a positive integer; default is 1).
            waypoints_ids (dict): A dictionary mapping node IDs to simulation waypoint IDs (default is an empty dictionary).
            journeys_ids (dict): A dictionary mapping journey identifiers to a tuple (journey_id, path).
                                 Default is an empty dictionary.
        """
        self._simulation = simulation
        self.every_nth_frame = every_nth_frame  # Uses the setter for validation.
        self.waypoints_ids = waypoints_ids if waypoints_ids is not None else {}
        self.journeys_ids = journeys_ids if journeys_ids is not None else {}

    # Getter and Setter for simulation
    @property
    def simulation(self):
        """Gets the simulation object or value."""
        return self._simulation

    @simulation.setter
    def simulation(self, value):
        """Sets the simulation object or value."""
        self._simulation = value

    # Getter and Setter for every_nth_frame
    @property
    def every_nth_frame(self):
        """Gets the frame processing frequency (every nth frame)."""
        return self._every_nth_frame

    @every_nth_frame.setter
    def every_nth_frame(self, value):
        """
        Sets the frame processing frequency.
        Ensures that the value is a positive integer.
        """
        if isinstance(value, int) and value > 0:
            self._every_nth_frame = value
        else:
            raise ValueError("every_nth_frame must be a positive integer.")

    # Getter and Setter for waypoints_ids
    @property
    def waypoints_ids(self):
        """Gets the dictionary mapping node IDs to simulation waypoint IDs."""
        return self._waypoints_ids

    @waypoints_ids.setter
    def waypoints_ids(self, value):
        """
        Sets the dictionary mapping node IDs to simulation waypoint IDs.

        Args:
            value (dict): A dictionary mapping node IDs to waypoint IDs.

        Raises:
            ValueError: If value is not a dictionary.
        """
        if isinstance(value, dict):
            self._waypoints_ids = value
        else:
            raise ValueError("waypoints_ids must be a dictionary.")

    # Getter and Setter for journeys_ids
    @property
    def journeys_ids(self):
        """
        Gets the dictionary mapping journey identifiers to a tuple (journey_id, path).

        Each key must be a string, and each value must be a tuple of two elements:
            - The first element is the journey ID.
            - The second element is the path (e.g., a list of nodes).
        """
        return self._journeys_ids

    @journeys_ids.setter
    def journeys_ids(self, value):
        """
        Sets the dictionary mapping journey identifiers to a tuple (journey_id, path).

        Args:
            value (dict): A dictionary where keys are strings and values are tuples of the form (journey_id, path).

        Raises:
            ValueError: If value is not a dictionary, or if any key is not a string,
                        or if any value is not a tuple of length 2.
        """
        if not isinstance(value, dict):
            raise ValueError("journeys_ids must be a dictionary.")
        for key, tup in value.items():
            if not isinstance(key, str):
                raise ValueError("All keys in journeys_ids must be strings.")
            #if not (isinstance(tup, tuple) and len(tup) == 2):
                #raise ValueError("Each value in journeys_ids must be a tuple of (journey_id, path).")
        self._journeys_ids = value

    def __str__(self):
        """
        Returns a string representation of the simulation configuration.
        """
        return (f"SimulationConfig(simulation={self._simulation}, "
                f"every_nth_frame={self._every_nth_frame}, "
                f"waypoints_ids={self._waypoints_ids}, "
                f"journeys_ids={self._journeys_ids})")


# Example usage:
if __name__ == "__main__":
    # Example journeys_ids where the key is a journey identifier and the value is a tuple (journey_id, path)
    example_journeys_ids = {
        "journey1": (201, ["A", "B", "C"]),
        "journey2": (202, ["D", "E", "F"])
    }

    config = SimulationConfig(simulation="MySimulation", every_nth_frame=5,
                              waypoints_ids={"A": 101, "B": 102},
                              journeys_ids=example_journeys_ids)
    print(config)
