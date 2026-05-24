from __future__ import annotations

import math
from typing import Any


def apply_edge_capacity_multiplier(
    graph: Any,
    multiplier: float,
) -> None:
    """
    Apply a capacity multiplier to all graph edges.

    The original edge capacity is preserved in `base_capacity`.
    If multiplier is 1.0, the graph is left unchanged.
    """

    if multiplier <= 0:
        raise ValueError("Edge capacity multiplier must be > 0")

    if multiplier == 1.0:
        return

    for _, _, edge_data in graph.edges(data=True):
        base_capacity = int(
            edge_data.get(
                "base_capacity",
                edge_data.get("capacity", 1),
            )
        )

        edge_data["base_capacity"] = base_capacity
        edge_data["capacity"] = max(
            1,
            int(math.ceil(base_capacity * multiplier)),
        )
        edge_data["capacity_multiplier"] = multiplier