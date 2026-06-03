from __future__ import annotations


def add_edges_with_flow_capacity(G, edges):
    """
    Add directed graph edges with static cost and edge flow capacity.

    Expected edge tuple:
        (source, target, cost, flow_capacity)
    """
    G.add_edges_from([
        (
            source,
            target,
            {
                "cost": cost,
                "flow_capacity": flow_capacity,
                "flow_occupancy": 0,
            },
        )
        for source, target, cost, flow_capacity in edges
    ])