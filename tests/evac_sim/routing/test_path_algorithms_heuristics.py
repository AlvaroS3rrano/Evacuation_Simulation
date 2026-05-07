import pytest
import networkx as nx

from evac_sim.routing.path_algorithms import (
    collect_k_shortest_paths,
    compute_path_effective_cost,
)


def _build_test_graph():
    G = nx.DiGraph()

    # Route 1: A -> B -> D
    G.add_edge("A", "B", cost=1.0, occupancy=10, capacity=5)
    G.add_edge("B", "D", cost=1.0, occupancy=0, capacity=5)

    # Route 2: A -> C -> D
    G.add_edge("A", "C", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("C", "D", cost=1.0, occupancy=0, capacity=5)

    return G


def test_collect_k_shortest_paths_none_keeps_base_cost_ranking():
    G = _build_test_graph()

    paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="none",
        beta=2.0,
        group_size=4,
    )

    assert paths
    returned_paths = [tuple(path) for path, _ in paths]

    assert ("A", "B", "D") in returned_paths
    assert ("A", "C", "D") in returned_paths

    cost_by_path = {tuple(path): cost for path, cost in paths}
    assert cost_by_path[("A", "B", "D")] == 2.0
    assert cost_by_path[("A", "C", "D")] == 2.0


def test_collect_k_shortest_paths_h1_penalizes_congested_route():
    G = _build_test_graph()

    paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h1",
        beta=2.0,
        group_size=4,
    )

    assert paths
    cost_by_path = {tuple(path): cost for path, cost in paths}

    assert cost_by_path[("A", "C", "D")] < cost_by_path[("A", "B", "D")]


def test_collect_k_shortest_paths_h1_prefers_less_congested_path_first():
    G = _build_test_graph()

    paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h1",
        beta=2.0,
        group_size=4,
    )

    assert paths[0][0] == ["A", "C", "D"]


def test_collect_k_shortest_paths_h2_penalizes_congested_route_inside_horizon():
    G = _build_test_graph()

    paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h2",
        beta=2.0,
        group_size=4,
        horizon_k=1,
    )

    assert paths
    cost_by_path = {tuple(path): cost for path, cost in paths}

    assert cost_by_path[("A", "C", "D")] < cost_by_path[("A", "B", "D")]


def test_collect_k_shortest_paths_h2_prefers_less_congested_path_first_inside_horizon():
    G = _build_test_graph()

    paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h2",
        beta=2.0,
        group_size=4,
        horizon_k=1,
    )

    assert paths[0][0] == ["A", "C", "D"]


def test_collect_k_shortest_paths_h1_and_h2_match_when_horizon_covers_full_path():
    G = _build_test_graph()

    h1_paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h1",
        beta=2.0,
        group_size=4,
    )

    h2_paths = collect_k_shortest_paths(
        G,
        "A",
        ["D"],
        heuristic="h2",
        beta=2.0,
        group_size=4,
        horizon_k=2,
    )

    assert h1_paths == h2_paths


def test_compute_path_effective_cost_none_returns_base_path_cost():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=10, capacity=5)
    G.add_edge("B", "C", cost=2.0, occupancy=10, capacity=5)
    G.add_edge("C", "D", cost=3.0, occupancy=10, capacity=5)

    cost = compute_path_effective_cost(
        G,
        ["A", "B", "C", "D"],
        heuristic="none",
        beta=2.0,
        group_size=5,
        horizon_k=1,
    )

    assert cost == pytest.approx(6.0)


def test_compute_path_effective_cost_h1_projects_group_over_full_path():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("B", "C", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("C", "D", cost=1.0, occupancy=0, capacity=5)

    cost = compute_path_effective_cost(
        G,
        ["A", "B", "C", "D"],
        heuristic="h1",
        beta=2.0,
        group_size=5,
        horizon_k=1,
    )

    # h1 ignores horizon_k:
    # each edge costs 1 + 2 * ((0 + 5) / 5) = 3
    assert cost == pytest.approx(9.0)


def test_compute_path_effective_cost_h2_projects_group_only_inside_horizon():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("B", "C", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("C", "D", cost=1.0, occupancy=0, capacity=5)

    cost = compute_path_effective_cost(
        G,
        ["A", "B", "C", "D"],
        heuristic="h2",
        beta=2.0,
        group_size=5,
        horizon_k=1,
    )

    # First edge inside the horizon:
    # 1 + 2 * ((0 + 5) / 5) = 3
    #
    # Second and third edges outside the horizon:
    # 1 + 2 * ((0 + 0) / 5) = 1 each
    assert cost == pytest.approx(5.0)


def test_compute_path_effective_cost_h2_includes_existing_occupancy_beyond_horizon():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("B", "C", cost=1.0, occupancy=10, capacity=5)
    G.add_edge("C", "D", cost=1.0, occupancy=0, capacity=5)

    cost = compute_path_effective_cost(
        G,
        ["A", "B", "C", "D"],
        heuristic="h2",
        beta=2.0,
        group_size=5,
        horizon_k=1,
    )

    # A->B is inside the horizon:
    # 1 + 2 * ((0 + 5) / 5) = 3
    #
    # B->C is outside the horizon, but keeps existing occupancy:
    # 1 + 2 * ((10 + 0) / 5) = 5
    #
    # C->D is outside the horizon:
    # 1 + 2 * ((0 + 0) / 5) = 1
    assert cost == pytest.approx(9.0)


def test_compute_path_effective_cost_h2_with_zero_horizon_does_not_project_group():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=0, capacity=5)
    G.add_edge("B", "C", cost=1.0, occupancy=0, capacity=5)

    cost = compute_path_effective_cost(
        G,
        ["A", "B", "C"],
        heuristic="h2",
        beta=2.0,
        group_size=5,
        horizon_k=0,
    )

    assert cost == pytest.approx(2.0)


def test_compute_path_effective_cost_h2_requires_horizon_k():
    G = nx.DiGraph()
    G.add_edge("A", "B", cost=1.0, occupancy=0, capacity=5)

    with pytest.raises(ValueError):
        compute_path_effective_cost(
            G,
            ["A", "B"],
            heuristic="h2",
            beta=2.0,
            group_size=5,
            horizon_k=None,
        )


def test_collect_k_shortest_paths_h2_requires_horizon_k():
    G = _build_test_graph()

    with pytest.raises(ValueError):
        collect_k_shortest_paths(
            G,
            "A",
            ["D"],
            heuristic="h2",
            beta=2.0,
            group_size=4,
            horizon_k=None,
        )