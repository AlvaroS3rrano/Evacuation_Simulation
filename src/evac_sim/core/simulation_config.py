from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SimulationConfig:
    """
    Configuration parameters controlling the behavior of a simulation.

    Attributes
    ----------
    simulation:
        Reference to the simulation object.

    every_nth_frame_simulation:
        Number of simulation frames between simulation updates.

    every_nth_frame_animation:
        Number of frames between animation updates.

    waypoints_ids:
        Mapping between graph node IDs and simulation waypoint IDs.

    exit_ids:
        Mapping between exit names and node identifiers.

    gamma:
        Threshold used when selecting paths.

    normal_max_speed:
        Maximum allowed pedestrian speed under normal conditions.

    stairs_max_speed:
        Maximum allowed pedestrian speed when using stairs.
    """

    simulation: Any = None
    every_nth_frame_simulation: int = 4
    every_nth_frame_animation: int = 50
    waypoints_ids: dict[str, Any] = field(default_factory=dict)
    exit_ids: dict[str, Any] = field(default_factory=dict)
    gamma: float = 0.4
    normal_max_speed: float = 1.0
    stairs_max_speed: float = 0.5

    def __post_init__(self) -> None:
        if self.every_nth_frame_simulation <= 0:
            raise ValueError("every_nth_frame_simulation must be > 0")

        if self.every_nth_frame_animation <= 0:
            raise ValueError("every_nth_frame_animation must be > 0")

        if self.gamma < 0:
            raise ValueError("gamma must be >= 0")

        if self.normal_max_speed <= 0:
            raise ValueError("normal_max_speed must be > 0")

        if self.stairs_max_speed <= 0:
            raise ValueError("stairs_max_speed must be > 0")

    @property
    def exit_names(self) -> list[str]:
        """Return the list of exit identifiers defined in the configuration."""
        return list(self.exit_ids.keys())