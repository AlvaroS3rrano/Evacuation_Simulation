import networkx as nx
import pytest

from evac_sim.orchestration.congestion_config import CongestionConfig
from evac_sim.orchestration.edge_capacity import (
    apply_congestion_settings_to_graph,
    apply_edge_capacity_multiplier,
)


def test_apply_edge_capacity_multiplier_keeps_capacity_unchanged_for_multiplier_one():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", capacity=4, cost=10.0)

    apply_edge_capacity_multiplier(graph, 1.0)

    assert graph["1"]["2"]["capacity"] == 4
    assert graph["1"]["2"]["cost"] == 10.0
    assert "base_capacity" not in graph["1"]["2"]
    assert "capacity_multiplier" not in graph["1"]["2"]


def test_apply_edge_capacity_multiplier_doubles_capacity():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", capacity=4, cost=10.0)
    graph.add_edge("2", "3", capacity=25, cost=5.0)

    apply_edge_capacity_multiplier(graph, 2.0)

    assert graph["1"]["2"]["base_capacity"] == 4
    assert graph["1"]["2"]["capacity"] == 8
    assert graph["1"]["2"]["capacity_multiplier"] == 2.0
    assert graph["1"]["2"]["cost"] == 10.0

    assert graph["2"]["3"]["base_capacity"] == 25
    assert graph["2"]["3"]["capacity"] == 50
    assert graph["2"]["3"]["capacity_multiplier"] == 2.0
    assert graph["2"]["3"]["cost"] == 5.0


def test_apply_edge_capacity_multiplier_uses_default_capacity_when_missing():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", cost=10.0)

    apply_edge_capacity_multiplier(graph, 2.0)

    assert graph["1"]["2"]["base_capacity"] == 1
    assert graph["1"]["2"]["capacity"] == 2
    assert graph["1"]["2"]["capacity_multiplier"] == 2.0


def test_apply_edge_capacity_multiplier_uses_existing_base_capacity_if_present():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", base_capacity=4, capacity=8, cost=10.0)

    apply_edge_capacity_multiplier(graph, 3.0)

    assert graph["1"]["2"]["base_capacity"] == 4
    assert graph["1"]["2"]["capacity"] == 12
    assert graph["1"]["2"]["capacity_multiplier"] == 3.0


def test_apply_edge_capacity_multiplier_rejects_invalid_multiplier():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", capacity=4)

    with pytest.raises(ValueError, match="Edge capacity multiplier must be > 0"):
        apply_edge_capacity_multiplier(graph, 0)


def test_apply_congestion_settings_to_graph_sets_linear_policy_flags():
    graph = nx.DiGraph()
    graph.add_edge("1", "2", capacity=4, cost=10.0)

    apply_congestion_settings_to_graph(
        graph,
        CongestionConfig(
            edge_capacity_multiplier=2.0,
            use_linear_congestion_cost=True,
            block_edges_at_capacity=True,
        ),
    )

    assert graph["1"]["2"]["base_capacity"] == 4
    assert graph["1"]["2"]["capacity"] == 8
    assert graph["1"]["2"]["capacity_multiplier"] == 2.0
    assert graph["1"]["2"]["use_linear_congestion_cost"] is True
    assert graph["1"]["2"]["block_edges_at_capacity"] is True