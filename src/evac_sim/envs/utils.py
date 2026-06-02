def add_edges_with_capacity(G, edges):
    G.add_edges_from([
        (
            u,
            v,
            {
                "cost": c,
                "flow_capacity": flow_capacity,
                "occupancy": 0,
            },
        )
        for u, v, c, flow_capacity in edges
    ])