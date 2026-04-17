import networkx as nx

from evac_sim.routing.path_algorithms import collect_k_shortest_paths


def _build_test_graph():
    G = nx.DiGraph()

    # Ruta 1: A -> B -> D
    G.add_edge("A", "B", cost=1.0, occupancy=10, capacity=5)
    G.add_edge("B", "D", cost=1.0, occupancy=0, capacity=5)

    # Ruta 2: A -> C -> D
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