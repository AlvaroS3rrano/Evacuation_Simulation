from __future__ import annotations


def compute_effective_edge_cost(
    edge_data: dict,
    heuristic: str = "none",
    beta: float = 1.0,
    group_size: int = 0,
) -> float:
    if heuristic is None:
        heuristic = "none"

    base_cost = edge_data["cost"]

    if heuristic == "none":
        return base_cost

    capacity = max(1, int(edge_data.get("capacity", 1)))
    occupancy = int(edge_data.get("occupancy", 0))
    projected_occupancy = occupancy + max(0, int(group_size))
    projected_ratio = projected_occupancy / capacity

    if heuristic in {"h1", "h2"}:
        if (
            edge_data.get("block_edges_at_capacity", False)
            and projected_occupancy > capacity
        ):
            return float("inf")

        if edge_data.get("use_linear_congestion_cost", False):
            return base_cost * (1.0 + beta * projected_ratio)

        # Legacy behavior kept for backward compatibility when no `congestion`
        # section is provided in the config.
        return base_cost + beta * projected_ratio

    if heuristic == "h3":
        # h3 is evaluated at full-path level because temporal capacity depends
        # on the estimated arrival time to each future edge/node.
        return base_cost

    raise ValueError(f"Unknown heuristic: {heuristic}")