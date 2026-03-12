from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EnvironmentInfo:
    """
    Contains structural information about the evacuation environment.

    Attributes
    ----------
    graph:
        Graph representing the environment topology.

    paths_connection:
        Database connection used to retrieve path information.

    floors:
        Optional structure describing the floors of the environment.

    floor_number:
        Total number of floors in the environment.

    floor_connecting_nodes:
        Mapping describing nodes that connect different floors
        (e.g. stairs or elevators).

    floor_paths:
        Precomputed paths for each floor.
    """

    graph: Any
    paths_connection: Any
    floors: Any = None
    floor_number: int = 1
    floor_connecting_nodes: dict[Any, Any] = field(default_factory=dict)
    floor_paths: dict[Any, Any] = field(default_factory=dict)