from evac_sim.routing.heuristics import compute_effective_edge_cost


def test_heuristic_none_returns_base_cost():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 3,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": True,
    }

    assert compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="none",
        beta=2.0,
        group_size=3,
    ) == 10.0


def test_legacy_h1_cost_is_preserved_when_linear_policy_is_disabled():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 1,
        "use_linear_congestion_cost": False,
        "block_edges_at_capacity": False,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=2.0,
        group_size=1,
    )

    # projected_ratio = (1 + 1) / 4 = 0.5
    # legacy cost = 10 + 2 * 0.5 = 11
    assert cost == 11.0


def test_linear_h1_cost_uses_multiplicative_linear_penalty():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 1,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": False,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=2.0,
        group_size=1,
    )

    # projected_ratio = (1 + 1) / 4 = 0.5
    # linear cost = 10 * (1 + 2 * 0.5) = 20
    assert cost == 20.0


def test_linear_h2_cost_uses_same_policy():
    edge_data = {
        "cost": 10.0,
        "capacity": 5,
        "occupancy": 2,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": False,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h2",
        beta=1.0,
        group_size=2,
    )

    # projected_ratio = (2 + 2) / 5 = 0.8
    # linear cost = 10 * (1 + 1 * 0.8) = 18
    assert cost == 18.0


def test_saturated_edge_is_allowed_when_projected_occupancy_equals_capacity():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 2,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": True,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    # projected_occupancy = 4, capacity = 4
    # exact capacity is allowed
    assert cost != float("inf")
    assert cost == 20.0


def test_edge_is_blocked_when_projected_occupancy_exceeds_capacity():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 3,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": True,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    assert cost == float("inf")


def test_edge_is_not_blocked_when_blocking_policy_is_disabled():
    edge_data = {
        "cost": 10.0,
        "capacity": 4,
        "occupancy": 3,
        "use_linear_congestion_cost": True,
        "block_edges_at_capacity": False,
    }

    cost = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    # projected_ratio = 5 / 4 = 1.25
    # linear cost = 10 * (1 + 1.25) = 22.5
    assert cost == 22.5