from __future__ import annotations


def _positive_int(value, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return max(1, int(default))


def _non_negative_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def compute_effective_step_cost(
    *,
    edge_data: dict,
    target_node_data: dict,
    heuristic: str = "none",
    beta: float = 1.0,
    group_size: int = 0,
) -> float:
    """
    Compute static congestion cost for one path step u -> v.

    h1/h2:
      - edge flow capacity: flow_occupancy / flow_capacity
      - target node capacity: node_occupancy / node_capacity

    h3 is evaluated at full-path temporal level.
    """
    if heuristic is None:
        heuristic = "none"

    base_cost = float(edge_data["cost"])

    if heuristic in {"none", "h3"}:
        return base_cost

    if heuristic not in {"h1", "h2"}:
        raise ValueError(f"Unknown heuristic: {heuristic}")

    projected_group_size = _non_negative_int(group_size)

    flow_capacity = _positive_int(
        edge_data.get("flow_capacity", 1),
        default=1,
    )
    flow_occupancy = _non_negative_int(
        edge_data.get("flow_occupancy", 0),
        default=0,
    )

    node_capacity = _positive_int(
        target_node_data.get("node_capacity", 1),
        default=1,
    )
    node_occupancy = _non_negative_int(
        target_node_data.get("node_occupancy", 0),
        default=0,
    )

    projected_flow_occupancy = flow_occupancy + projected_group_size
    projected_node_occupancy = node_occupancy + projected_group_size

    flow_ratio = projected_flow_occupancy / flow_capacity
    node_ratio = projected_node_occupancy / node_capacity

    # A path step is constrained by its worst bottleneck: either the passage
    # flow capacity or the destination area capacity.
    projected_ratio = max(flow_ratio, node_ratio)

    if edge_data.get("block_edges_at_capacity", False) and (
        projected_flow_occupancy > flow_capacity
        or projected_node_occupancy > node_capacity
    ):
        return float("inf")

    if edge_data.get("use_linear_congestion_cost", False):
        return base_cost * (1.0 + beta * projected_ratio)

    return base_cost + beta * projected_ratio