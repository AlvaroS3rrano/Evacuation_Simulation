import networkx as nx
import pytest

from evac_sim.routing.decision_policies import (
    compute_high_awareness_alternative_path,
    compute_low_awareness_alternative_path,
)
from evac_sim.routing.multifloor_paths import (
    _filter_complete_by_gamma,
    _rescore_complete_paths,
    _sort_complete,
    getTargetsForCurrentNode,
)
from evac_sim.routing.path_algorithms import centrality_measures


class DummyEnv:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.floors = None
        self.floor_number = 2
        self.floor_connecting_nodes = {}
        self.paths_connection = None
        self.floor_paths = {}


class DummyGroup:
    def __init__(self, path=None, algorithm=0, awareness_level=0):
        self.path = path
        self.algorithm = algorithm
        self.awareness_level = awareness_level
        self.blocked_nodes = []
        self.wait_until_node = None
        self.current_nodes = {}


def test_centrality_measures_uses_geometric_mean():
    G = nx.DiGraph()
    G.add_nodes_from(["A", "B", "C", "D", "E"])

    all_paths = [
        (["A", "B", "D"], 2.0),
        (["A", "C", "D"], 2.0),
        (["A", "B", "E", "D"], 3.0),
    ]

    node_centrality, scored = centrality_measures(G, all_paths)

    assert pytest.approx(node_centrality["B"], rel=1e-9) == 2 / 3
    assert pytest.approx(node_centrality["C"], rel=1e-9) == 1 / 3
    assert pytest.approx(node_centrality["E"], rel=1e-9) == 1 / 3

    scores = {tuple(path): score for path, _, score in scored}

    assert pytest.approx(scores[("A", "B", "D")], rel=1e-9) == 2 / 3
    assert pytest.approx(scores[("A", "C", "D")], rel=1e-9) == 1 / 3
    assert pytest.approx(scores[("A", "B", "E", "D")], rel=1e-9) == ((2 / 3) * (1 / 3)) ** 0.5


def test_filter_complete_by_gamma_keeps_only_admissible_paths():
    complete = [
        (["A", "B", "X"], 10.0),
        (["A", "C", "X"], 11.0),
        (["A", "D", "X"], 14.0),
    ]

    filtered = _filter_complete_by_gamma(complete, gamma=0.1)
    filtered_paths = [tuple(path) for path, _ in filtered]

    assert ("A", "B", "X") in filtered_paths
    assert ("A", "C", "X") in filtered_paths
    assert ("A", "D", "X") not in filtered_paths


def test_sort_complete_agile_uses_rescored_final_set():
    env = DummyEnv()
    env.graph.add_nodes_from(["A", "B", "C", "D", "X"])

    complete = [
        (["A", "B", "X"], 10.0),
        (["A", "C", "X"], 10.0),
        (["A", "B", "D", "X"], 10.5),
    ]

    rescored = _rescore_complete_paths(env, complete)
    sorted_paths = _sort_complete(rescored, algo=1)
    sorted_only = [tuple(path) for path, _, _ in sorted_paths]

    assert sorted_only[0] == ("A", "B", "X")


def test_get_targets_for_current_node_includes_same_floor_and_connectors():
    env = DummyEnv()
    env.graph.add_nodes_from(
        [
            ("n1", {"floor": 0}),
            ("e0", {"floor": 0}),
            ("c_up", {"floor": 1}),
            ("c_down", {"floor": 0}),
        ]
    )
    env.floor_connecting_nodes = {
        (0, 1): ["c_up"],
        (0, -1): [],
    }

    targets = getTargetsForCurrentNode(env, "n1", 0, exits=["e0"])
    assert "e0" in targets
    assert "c_up" in targets
    assert "n1" not in targets


def test_low_awareness_only_reacts_to_next_node(monkeypatch):
    env = DummyEnv()
    group = DummyGroup(path=["A", "B", "X"], algorithm=0, awareness_level=0)

    called = {"updated": False}

    def fake_update_all_graph_risks(env_, risk_map):
        called["updated"] = True

    def fake_get_possible_paths(env_, current_node, exits, gamma, algo, blocked_nodes=None):
        return [["A", "C", "X"], ["A", "D", "X"]]

    monkeypatch.setattr(
        "evac_sim.routing.decision_policies.update_all_graph_risks",
        fake_update_all_graph_risks,
    )
    monkeypatch.setattr(
        "evac_sim.routing.decision_policies.getPosiblePaths",
        fake_get_possible_paths,
    )

    risk_per_node = {"B": 0.8, "C": 0.1, "D": 0.1}

    best = compute_low_awareness_alternative_path(
        exits=["X"],
        risk_per_node=risk_per_node,
        next_node="B",
        current_node="A",
        agent_group=group,
        EnvInf=env,
        gamma=0.4,
        risk_threshold=0.5,
    )

    assert called["updated"] is True
    assert best == ["A", "C", "X"]
    assert "B" in group.blocked_nodes


def test_high_awareness_reacts_to_any_remaining_unsafe_node(monkeypatch):
    env = DummyEnv()
    group = DummyGroup(path=["A", "B", "C", "X"], algorithm=0, awareness_level=1)

    def fake_update_all_graph_risks(env_, risk_map):
        return None

    def fake_get_possible_paths(env_, current_node, exits, gamma, algo, blocked_nodes=None):
        return [["A", "D", "X"], ["A", "E", "X"]]

    monkeypatch.setattr(
        "evac_sim.routing.decision_policies.update_all_graph_risks",
        fake_update_all_graph_risks,
    )
    monkeypatch.setattr(
        "evac_sim.routing.decision_policies.getPosiblePaths",
        fake_get_possible_paths,
    )

    risk_per_node = {"B": 0.1, "C": 0.9, "D": 0.1, "E": 0.1}

    best = compute_high_awareness_alternative_path(
        exits=["X"],
        risk_per_node=risk_per_node,
        current_node="A",
        agent_group=group,
        EnvInf=env,
        gamma=0.4,
        risk_threshold=0.5,
    )

    assert best == ["A", "D", "X"]
    assert "C" in group.blocked_nodes


def test_efficient_sort_prefers_lowest_cost():
    complete = [
        (["A", "C", "X"], 11.0, 0.7),
        (["A", "B", "X"], 10.0, 0.6),
        (["A", "D", "X"], 10.5, 0.9),
    ]

    sorted_paths = _sort_complete(complete, algo=0)
    assert tuple(sorted_paths[0][0]) == ("A", "B", "X")