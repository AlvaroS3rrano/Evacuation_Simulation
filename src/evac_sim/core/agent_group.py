from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentGroup:
    """
    Group of agents sharing the same evacuation path and routing behaviour.

    Attributes
    ----------
    agents:
        List of agent identifiers belonging to the group.

    path:
        Planned path for the group as a sequence of nodes.

    current_nodes:
        Mapping from each agent identifier to its current node.

    algorithm:
        Routing algorithm identifier:
        0 -> shortest path
        1 -> centrality-based path

    awareness_level:
        Information awareness level of the agents:
        0 -> agents only learn changes when reaching a neighbouring node
        1 -> agents know changes immediately

    blocked_nodes:
        List of currently blocked nodes affecting the group.

    wait_until_node:
        Node where the sistem can continue with path-related logic.

    agents_in_stairs:
        List of agent identifiers currently located on stairs.

    initial_agent_id:
        Identifier of the initial or reference agent for the group.
    """

    agents: list[Any]
    path: list[Any]
    current_nodes: dict[Any, Any]
    algorithm: int
    awareness_level: int
    blocked_nodes: list[Any] = field(default_factory=list)
    wait_until_node: Any = None
    agents_in_stairs: list[Any] = field(default_factory=list)
    initial_agents_ids: list[Any] = field(default_factory=list)
    reserved_edges: set[tuple[Any, Any]] = field(default_factory=set)
    reserved_group_size: int = 0

    waiting_due_to_congestion: bool = False
    waiting_since_frame: int | None = None
    no_path_count: int = 0

    def __post_init__(self) -> None:
        if self.algorithm not in (0, 1):
            raise ValueError("algorithm must be 0 (shortest path) or 1 (centrality-based path)")
        if self.awareness_level not in (0, 1):
            raise ValueError("awareness_level must be 0 or 1")