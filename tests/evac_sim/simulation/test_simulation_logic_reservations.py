import networkx as nx

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation.simulation_logic import (
    get_remaining_path_for_group,
    update_group_reserved_edges,
)


class DummyEnv:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.graph.add_edge("A", "B", occupancy=0, capacity=5, cost=1.0)
        self.graph.add_edge("B", "C", occupancy=0, capacity=5, cost=1.0)
        self.graph.add_edge("C", "D", occupancy=0, capacity=5, cost=1.0)
        self.graph.add_edge("B", "X", occupancy=0, capacity=5, cost=1.0)
        self.graph.add_edge("X", "D", occupancy=0, capacity=5, cost=1.0)


def build_group(path, current_nodes, agents=None):
    if agents is None:
        agents = [1, 2]

    group = AgentGroup(
        agents=agents,
        path=path,
        current_nodes=current_nodes,
        algorithm=0,
        awareness_level=0,
    )
    group.reserved_edges = set()
    group.reserved_group_size = 0
    group.initial_agents_ids = list(agents)
    return group


def test_get_remaining_path_for_group_uses_most_advanced_agent():
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "C"},
        agents=[1, 2],
    )

    remaining = get_remaining_path_for_group(group)

    assert remaining == ["C", "D"]


def test_update_group_reserved_edges_reserves_full_remaining_path_initially():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_reserved_edges(env, group, frame=0, group_id="g1")

    assert env.graph["A"]["B"]["occupancy"] == 2
    assert env.graph["B"]["C"]["occupancy"] == 2
    assert env.graph["C"]["D"]["occupancy"] == 2
    assert group.reserved_edges == {("A", "B"), ("B", "C"), ("C", "D")}
    assert group.reserved_group_size == 2


def test_update_group_reserved_edges_releases_passed_edges_when_group_advances():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_reserved_edges(env, group, frame=0, group_id="g1")

    group.current_nodes = {1: "B", 2: "B"}
    update_group_reserved_edges(env, group, frame=1, group_id="g1")

    assert env.graph["A"]["B"]["occupancy"] == 0
    assert env.graph["B"]["C"]["occupancy"] == 2
    assert env.graph["C"]["D"]["occupancy"] == 2
    assert group.reserved_edges == {("B", "C"), ("C", "D")}


def test_update_group_reserved_edges_replaces_reservation_after_reroute():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "B"},
        agents=[1, 2],
    )

    update_group_reserved_edges(env, group, frame=0, group_id="g1")

    group.path = ["A", "B", "X", "D"]
    group.current_nodes = {1: "B", 2: "B"}

    update_group_reserved_edges(env, group, frame=1, group_id="g1")

    assert env.graph["B"]["C"]["occupancy"] == 0
    assert env.graph["C"]["D"]["occupancy"] == 0
    assert env.graph["B"]["X"]["occupancy"] == 2
    assert env.graph["X"]["D"]["occupancy"] == 2
    assert group.reserved_edges == {("B", "X"), ("X", "D")}


def test_update_group_reserved_edges_adjusts_occupancy_when_group_size_changes():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_reserved_edges(env, group, frame=0, group_id="g1")

    group.agents = [1]
    group.current_nodes = {1: "A"}

    update_group_reserved_edges(env, group, frame=1, group_id="g1")

    assert env.graph["A"]["B"]["occupancy"] == 1
    assert env.graph["B"]["C"]["occupancy"] == 1
    assert env.graph["C"]["D"]["occupancy"] == 1
    assert group.reserved_group_size == 1


def test_update_group_reserved_edges_never_makes_occupancy_negative():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_reserved_edges(env, group, frame=0, group_id="g1")

    group.agents = []
    group.current_nodes = {}

    update_group_reserved_edges(env, group, frame=2, group_id="g1")

    assert env.graph["A"]["B"]["occupancy"] >= 0
    assert env.graph["B"]["C"]["occupancy"] >= 0
    assert env.graph["C"]["D"]["occupancy"] >= 0