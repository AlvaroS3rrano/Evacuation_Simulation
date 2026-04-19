import pytest

from evac_sim.routing.heuristics import compute_effective_edge_cost


def test_compute_effective_edge_cost_none_returns_base_cost():
    edge_data = {"cost": 10.0, "occupancy": 3, "capacity": 5}

    result = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="none",
        beta=2.0,
        group_size=4,
    )

    assert result == 10.0


def test_compute_effective_edge_cost_h1_uses_projected_occupancy():
    edge_data = {"cost": 10.0, "occupancy": 3, "capacity": 5}

    result = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=2.0,
        group_size=4,
    )

    assert result == pytest.approx(10.0 + 2.0 * ((3 + 4) / 5))


def test_compute_effective_edge_cost_h1_uses_capacity_at_least_one():
    edge_data = {"cost": 8.0, "occupancy": 2, "capacity": 0}

    result = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h1",
        beta=1.5,
        group_size=3,
    )

    assert result == pytest.approx(8.0 + 1.5 * ((2 + 3) / 1))


def test_compute_effective_edge_cost_h2_uses_projected_occupancy():
    edge_data = {"cost": 10.0, "occupancy": 3, "capacity": 5}

    result = compute_effective_edge_cost(
        edge_data=edge_data,
        heuristic="h2",
        beta=2.0,
        group_size=4,
    )

    assert result == pytest.approx(10.0 + 2.0 * ((3 + 4) / 5))


def test_compute_effective_edge_cost_h3_raises_not_implemented():
    edge_data = {"cost": 10.0, "occupancy": 1, "capacity": 5}

    with pytest.raises(NotImplementedError):
        compute_effective_edge_cost(
            edge_data=edge_data,
            heuristic="h3",
            beta=1.0,
            group_size=1,
        )


def test_compute_effective_edge_cost_unknown_heuristic_raises_value_error():
    edge_data = {"cost": 10.0, "occupancy": 1, "capacity": 5}

    with pytest.raises(ValueError):
        compute_effective_edge_cost(
            edge_data=edge_data,
            heuristic="weird",
            beta=1.0,
            group_size=1,
        )