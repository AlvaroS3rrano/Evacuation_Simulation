class SimulationConfig:
    """
    A class representing configuration parameters for a simulation.

    Attributes:
        simulation (any): An object or value representing the simulation.
        every_nth_frame_simulation (int): The frequency (every nth simulation frame) at which simulation steps are processed.
        every_nth_frame_animation (int): The frequency (every nth animation frame) for updating the simulation display.
        waypoints_ids (dict): A dictionary mapping graph node IDs to simulation waypoint IDs.
        exit_ids (dict): A dictionary mapping exit names to node identifiers, representing points where the simulation might terminate or transition.
        gamma (float): A weighting parameter influencing the alternative path computation by controlling the trade-off between risk minimization and path optimality.
        normal_max_speed (float): The maximum speed allowed under normal conditions.
        stairs_max_speed (float): The maximum speed allowed when using stairs.
    """

    def __init__(self, simulation=None, every_nth_frame_simulation=4, every_nth_frame_animation=50,
                 waypoints_ids=None, exit_ids=None, gamma=0.4, normal_max_speed=1.0, stairs_max_speed=0.5):
        """
        Initializes the SimulationConfig with provided or default values.

        Args:
            simulation (any): The simulation object or identifier. Default is None.
            every_nth_frame_simulation (int): Frequency for processing simulation frames. Default is 4.
            every_nth_frame_animation (int): Frequency for updating animation frames. Default is 50.
            waypoints_ids (dict): A dictionary mapping node IDs to simulation waypoint IDs. Default is an empty dictionary.
            exit_ids (dict): A dictionary of exit IDs mapping exit names to node identifiers. Default is an empty dictionary.
            gamma (float): A weighting parameter for alternative path computation. Default is 0.4.
            normal_max_speed (float): The maximum speed under normal conditions. Default is 1.0.
            stairs_max_speed (float): The maximum speed when using stairs. Default is 0.5.
        """
        self.simulation = simulation
        self.every_nth_frame_simulation = every_nth_frame_simulation
        self.every_nth_frame_animation = every_nth_frame_animation
        self.waypoints_ids = waypoints_ids if waypoints_ids is not None else {}
        self.exit_ids = exit_ids if exit_ids is not None else {}
        self.gamma = gamma
        self.normal_max_speed = normal_max_speed
        self.stairs_max_speed = stairs_max_speed

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
                f"every_nth_frame_simulation={self.every_nth_frame_simulation}, "
                f"every_nth_frame_animation={self.every_nth_frame_animation}, "
                f"waypoints_ids={self.waypoints_ids}, "
                f"exit_ids={self.exit_ids}, "
                f"gamma={self.gamma}, "
                f"normal_max_speed={self.normal_max_speed}, "
                f"stairs_max_speed={self.stairs_max_speed})")


# Example usage:
if __name__ == "__main__":
    # Initialize exit_ids as a dictionary, e.g., mapping exit names to node identifiers
    example_exit_ids = {
        "exitA": "Node_A",
        "exitB": "Node_B"
    }

    config = SimulationConfig(simulation="MySimulation", every_nth_frame_simulation=5,
                              waypoints_ids={"A": 101, "B": 102},
                              exit_ids=example_exit_ids,
                              gamma=0.2,
                              normal_max_speed=1.2,
                              stairs_max_speed=0.7)
    print(config)
    print("Exit IDs keys:", config.get_exit_ids_keys())
