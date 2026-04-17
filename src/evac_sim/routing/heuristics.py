from __future__ import annotations

def compute_effective_edge_cost(
    edge_data: dict,
    heuristic: str = "none",
    beta: float = 1.0,
    group_size: int = 0,
) -> float:
    base_cost = edge_data["cost"]

    if heuristic == "none":
        return base_cost

    if heuristic == "h1":
        capacity = edge_data.get("capacity", 1)
        occupancy = edge_data.get("occupancy", 0)

        projected_ratio = (occupancy + group_size) / max(1, capacity)
        return base_cost + beta * projected_ratio

    if heuristic in {"h2", "h3"}:
        raise NotImplementedError(f"Heuristic '{heuristic}' not implemented yet.")

    raise ValueError(f"Unknown heuristic: {heuristic}")