def add_edges_with_capacity(G, edges):
    G.add_edges_from([
        (u, v, {
            "cost": c,
            "capacity": cap,
            "occupancy": 0
        })
        for u, v, c, cap in edges
    ])