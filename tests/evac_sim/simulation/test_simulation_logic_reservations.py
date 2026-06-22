import networkx as nx

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation.simulation_logic import (
    get_remaining_path_for_group,
    get_static_reservation_path_segment,
    update_group_static_reservations,
)


class DummyEnv:
    def __init__(self):
        self.graph = nx.DiGraph()

        for node in ["A", "B", "C", "D", "X"]:
            self.graph.add_node(
                node,
                node_capacity=5,
                node_occupancy=0,
            )

        self.graph.add_edge("A", "B", flow_occupancy=0, flow_capacity=5, cost=1.0)
        self.graph.add_edge("B", "C", flow_occupancy=0, flow_capacity=5, cost=1.0)
        self.graph.add_edge("C", "D", flow_occupancy=0, flow_capacity=5, cost=1.0)
        self.graph.add_edge("B", "X", flow_occupancy=0, flow_capacity=5, cost=1.0)
        self.graph.add_edge("X", "D", flow_occupancy=0, flow_capacity=5, cost=1.0)


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
    group.reserved_nodes = set()
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


def test_update_group_static_reservations_reserves_full_remaining_path_initially():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1")

    assert env.graph["A"]["B"]["flow_occupancy"] == 2
    assert env.graph["B"]["C"]["flow_occupancy"] == 2
    assert env.graph["C"]["D"]["flow_occupancy"] == 2

    assert env.graph.nodes["B"]["node_occupancy"] == 2
    assert env.graph.nodes["C"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 2

    assert group.reserved_edges == {("A", "B"), ("B", "C"), ("C", "D")}
    assert group.reserved_nodes == {"B", "C", "D"}
    assert group.reserved_group_size == 2


def test_update_group_static_reservations_releases_passed_edges_when_group_advances():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1")

    group.current_nodes = {1: "B", 2: "B"}
    update_group_static_reservations(env, group, frame=1, group_id="g1")

    assert env.graph["A"]["B"]["flow_occupancy"] == 0
    assert env.graph["B"]["C"]["flow_occupancy"] == 2
    assert env.graph["C"]["D"]["flow_occupancy"] == 2

    assert env.graph.nodes["B"]["node_occupancy"] == 0
    assert env.graph.nodes["C"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 2

    assert group.reserved_edges == {("B", "C"), ("C", "D")}
    assert group.reserved_nodes == {"C", "D"}


def test_update_group_static_reservations_replaces_reservation_after_reroute():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "B"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1")

    group.path = ["A", "B", "X", "D"]
    group.current_nodes = {1: "B", 2: "B"}

    update_group_static_reservations(env, group, frame=1, group_id="g1")

    assert env.graph["B"]["C"]["flow_occupancy"] == 0
    assert env.graph["C"]["D"]["flow_occupancy"] == 0
    assert env.graph["B"]["X"]["flow_occupancy"] == 2
    assert env.graph["X"]["D"]["flow_occupancy"] == 2

    assert env.graph.nodes["C"]["node_occupancy"] == 0
    assert env.graph.nodes["X"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 2

    assert group.reserved_edges == {("B", "X"), ("X", "D")}
    assert group.reserved_nodes == {"X", "D"}


def test_update_group_static_reservations_adjusts_occupancy_when_group_size_changes():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1")

    group.agents = [1]
    group.current_nodes = {1: "A"}

    update_group_static_reservations(env, group, frame=1, group_id="g1")

    assert env.graph["A"]["B"]["flow_occupancy"] == 1
    assert env.graph["B"]["C"]["flow_occupancy"] == 1
    assert env.graph["C"]["D"]["flow_occupancy"] == 1

    assert env.graph.nodes["B"]["node_occupancy"] == 1
    assert env.graph.nodes["C"]["node_occupancy"] == 1
    assert env.graph.nodes["D"]["node_occupancy"] == 1

    assert group.reserved_group_size == 1


def test_update_group_static_reservations_never_makes_occupancy_negative():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1")

    group.agents = []
    group.current_nodes = {}

    update_group_static_reservations(env, group, frame=2, group_id="g1")

    assert env.graph["A"]["B"]["flow_occupancy"] >= 0
    assert env.graph["B"]["C"]["flow_occupancy"] >= 0
    assert env.graph["C"]["D"]["flow_occupancy"] >= 0

    assert env.graph.nodes["B"]["node_occupancy"] >= 0
    assert env.graph.nodes["C"]["node_occupancy"] >= 0
    assert env.graph.nodes["D"]["node_occupancy"] >= 0


def test_get_static_reservation_path_segment_without_horizon_returns_full_remaining_path():
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "B"},
        agents=[1, 2],
    )

    reserved_segment = get_static_reservation_path_segment(group, horizon_k=None)

    assert reserved_segment == ["B", "C", "D"]


def test_get_static_reservation_path_segment_with_horizon_1_returns_one_edge_ahead():
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "B"},
        agents=[1, 2],
    )

    reserved_segment = get_static_reservation_path_segment(group, horizon_k=1)

    assert reserved_segment == ["B", "C"]


def test_get_static_reservation_path_segment_with_horizon_2_returns_two_edges_ahead():
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    reserved_segment = get_static_reservation_path_segment(group, horizon_k=2)

    assert reserved_segment == ["A", "B", "C"]


def test_update_group_static_reservations_with_horizon_limits_reserved_edges_and_nodes():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1", horizon_k=1)

    assert env.graph["A"]["B"]["flow_occupancy"] == 2
    assert env.graph["B"]["C"]["flow_occupancy"] == 0
    assert env.graph["C"]["D"]["flow_occupancy"] == 0

    assert env.graph.nodes["B"]["node_occupancy"] == 2
    assert env.graph.nodes["C"]["node_occupancy"] == 0
    assert env.graph.nodes["D"]["node_occupancy"] == 0

    assert group.reserved_edges == {("A", "B")}
    assert group.reserved_nodes == {"B"}


def test_update_group_static_reservations_with_horizon_2_reserves_only_first_two_edges_and_nodes():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1", horizon_k=2)

    assert env.graph["A"]["B"]["flow_occupancy"] == 2
    assert env.graph["B"]["C"]["flow_occupancy"] == 2
    assert env.graph["C"]["D"]["flow_occupancy"] == 0

    assert env.graph.nodes["B"]["node_occupancy"] == 2
    assert env.graph.nodes["C"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 0

    assert group.reserved_edges == {("A", "B"), ("B", "C")}
    assert group.reserved_nodes == {"B", "C"}


def test_update_group_static_reservations_with_horizon_moves_window_when_group_advances():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1", horizon_k=1)

    group.current_nodes = {1: "B", 2: "B"}
    update_group_static_reservations(env, group, frame=1, group_id="g1", horizon_k=1)

    assert env.graph["A"]["B"]["flow_occupancy"] == 0
    assert env.graph["B"]["C"]["flow_occupancy"] == 2
    assert env.graph["C"]["D"]["flow_occupancy"] == 0

    assert env.graph.nodes["B"]["node_occupancy"] == 0
    assert env.graph.nodes["C"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 0

    assert group.reserved_edges == {("B", "C")}
    assert group.reserved_nodes == {"C"}


def test_update_group_static_reservations_with_horizon_replaces_window_after_reroute():
    env = DummyEnv()
    group = build_group(
        path=["A", "B", "C", "D"],
        current_nodes={1: "B", 2: "B"},
        agents=[1, 2],
    )

    update_group_static_reservations(env, group, frame=0, group_id="g1", horizon_k=1)

    group.path = ["A", "B", "X", "D"]
    group.current_nodes = {1: "B", 2: "B"}

    update_group_static_reservations(env, group, frame=1, group_id="g1", horizon_k=1)

    assert env.graph["B"]["C"]["flow_occupancy"] == 0
    assert env.graph["B"]["X"]["flow_occupancy"] == 2
    assert env.graph["X"]["D"]["flow_occupancy"] == 0

    assert env.graph.nodes["C"]["node_occupancy"] == 0
    assert env.graph.nodes["X"]["node_occupancy"] == 2
    assert env.graph.nodes["D"]["node_occupancy"] == 0

    assert group.reserved_edges == {("B", "X")}
    assert group.reserved_nodes == {"X"}