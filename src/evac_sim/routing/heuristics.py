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

    capacity = max(1, edge_data.get("capacity", 1))
    occupancy = edge_data.get("occupancy", 0)

    if heuristic in {"h1", "h2"}:
        projected_ratio = (occupancy + group_size) / capacity
        return base_cost + beta * projected_ratio

    if heuristic == "h3":
        raise NotImplementedError("Heuristic 'h3' not implemented yet.")

    raise ValueError(f"Unknown heuristic: {heuristic}")