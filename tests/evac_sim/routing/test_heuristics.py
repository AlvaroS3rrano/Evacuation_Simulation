from evac_sim.routing.heuristics import compute_effective_step_cost


def _edge_data(
    *,
    cost=10.0,
    flow_capacity=4,
    flow_occupancy=0,
    use_linear_congestion_cost=True,
    block_edges_at_capacity=False,
):
    return {
        "cost": cost,
        "flow_capacity": flow_capacity,
        "flow_occupancy": flow_occupancy,
        "use_linear_congestion_cost": use_linear_congestion_cost,
        "block_edges_at_capacity": block_edges_at_capacity,
    }


def _node_data(
    *,
    node_capacity=4,
    node_occupancy=0,
):
    return {
        "node_capacity": node_capacity,
        "node_occupancy": node_occupancy,
    }


def test_heuristic_none_returns_base_cost():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=3,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
    )
    target_node_data = _node_data(
        node_capacity=4,
        node_occupancy=3,
    )

    assert compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="none",
        beta=2.0,
        group_size=3,
    ) == 10.0


def test_additive_h1_cost_is_preserved_when_linear_policy_is_disabled():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=1,
        use_linear_congestion_cost=False,
        block_edges_at_capacity=False,
    )
    target_node_data = _node_data(
        node_capacity=4,
        node_occupancy=1,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=2.0,
        group_size=1,
    )

    # projected flow ratio = (1 + 1) / 4 = 0.5
    # projected node ratio = (1 + 1) / 4 = 0.5
    # projected ratio = max(0.5, 0.5) = 0.5
    # additive cost = 10 + 2 * 0.5 = 11
    assert cost == 11.0


def test_linear_h1_cost_uses_multiplicative_linear_penalty():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=1,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=False,
    )
    target_node_data = _node_data(
        node_capacity=4,
        node_occupancy=1,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=2.0,
        group_size=1,
    )

    # projected ratio = 0.5
    # linear cost = 10 * (1 + 2 * 0.5) = 20
    assert cost == 20.0


def test_linear_h2_cost_uses_same_policy():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=5,
        flow_occupancy=2,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=False,
    )
    target_node_data = _node_data(
        node_capacity=5,
        node_occupancy=2,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h2",
        beta=1.0,
        group_size=2,
    )

    # projected ratio = max((2 + 2) / 5, (2 + 2) / 5) = 0.8
    # linear cost = 10 * (1 + 1 * 0.8) = 18
    assert cost == 18.0


def test_exact_flow_capacity_is_allowed_when_projected_occupancy_equals_capacity():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=2,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
    )
    target_node_data = _node_data(
        node_capacity=10,
        node_occupancy=0,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    # projected flow occupancy = 4, flow_capacity = 4
    # exact capacity is allowed
    assert cost != float("inf")
    assert cost == 20.0


def test_step_is_blocked_when_projected_flow_exceeds_capacity():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=3,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
    )
    target_node_data = _node_data(
        node_capacity=10,
        node_occupancy=0,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    assert cost == float("inf")


def test_step_is_blocked_when_projected_node_occupancy_exceeds_capacity():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=10,
        flow_occupancy=0,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
    )
    target_node_data = _node_data(
        node_capacity=4,
        node_occupancy=3,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    assert cost == float("inf")


def test_step_is_not_blocked_when_blocking_policy_is_disabled():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=4,
        flow_occupancy=3,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=False,
    )
    target_node_data = _node_data(
        node_capacity=10,
        node_occupancy=0,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h1",
        beta=1.0,
        group_size=2,
    )

    # flow ratio = 5 / 4 = 1.25
    # node ratio = 2 / 10 = 0.2
    # projected ratio = 1.25
    # linear cost = 10 * (1 + 1.25) = 22.5
    assert cost == 22.5


def test_h3_returns_base_cost_at_step_level():
    edge_data = _edge_data(
        cost=10.0,
        flow_capacity=1,
        flow_occupancy=100,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
    )
    target_node_data = _node_data(
        node_capacity=1,
        node_occupancy=100,
    )

    cost = compute_effective_step_cost(
        edge_data=edge_data,
        target_node_data=target_node_data,
        heuristic="h3",
        beta=10.0,
        group_size=100,
    )

    assert cost == 10.0