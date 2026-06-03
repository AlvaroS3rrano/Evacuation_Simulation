from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation.group_state import (
    clear_group_waiting_due_to_congestion,
    mark_group_waiting_due_to_congestion,
    remaining_path_from_node,
    reservation_horizon_for_heuristic,
    safe_path_index,
    set_group_speed,
    uses_static_reservations,
)


def build_group():
    return AgentGroup(
        agents=[1, 2],
        path=["A", "B", "C"],
        current_nodes={1: "A", 2: "A"},
        algorithm=0,
        awareness_level=0,
    )


def test_reservation_horizon_for_heuristic_h1_returns_none():
    assert reservation_horizon_for_heuristic("h1", 5) is None


def test_reservation_horizon_for_heuristic_h2_uses_default_when_missing():
    assert reservation_horizon_for_heuristic("h2", None) == 3


def test_reservation_horizon_for_heuristic_h2_uses_explicit_value():
    assert reservation_horizon_for_heuristic("h2", 7) == 7


def test_uses_static_reservations_is_false_for_none():
    assert uses_static_reservations("none") is False


def test_uses_static_reservations_is_true_for_h1_and_h2():
    assert uses_static_reservations("h1") is True
    assert uses_static_reservations("h2") is True


def test_safe_path_index_returns_index_when_present():
    assert safe_path_index(["A", "B", "C"], "B") == 1


def test_safe_path_index_returns_minus_one_when_missing():
    assert safe_path_index(["A", "B", "C"], "X") == -1


def test_safe_path_index_returns_minus_one_for_none_path():
    assert safe_path_index(None, "A") == -1


def test_remaining_path_from_node_returns_empty_list_for_none_path():
    assert remaining_path_from_node(None, "A") == []


def test_remaining_path_from_node_returns_empty_list_for_none_node():
    assert remaining_path_from_node(["A", "B"], None) == []


def test_remaining_path_from_node_returns_suffix_when_node_exists():
    assert remaining_path_from_node(["A", "B", "C"], "B") == ["B", "C"]


def test_remaining_path_from_node_returns_full_path_when_node_is_missing():
    assert remaining_path_from_node(["A", "B", "C"], "X") == ["A", "B", "C"]


def test_mark_group_waiting_due_to_congestion_sets_state():
    group = build_group()

    mark_group_waiting_due_to_congestion(group, frame=10)

    assert group.waiting_due_to_congestion is True
    assert group.waiting_since_frame == 10
    assert group.no_path_count == 1


def test_mark_group_waiting_due_to_congestion_keeps_original_waiting_frame():
    group = build_group()

    mark_group_waiting_due_to_congestion(group, frame=10)
    mark_group_waiting_due_to_congestion(group, frame=20)

    assert group.waiting_since_frame == 10
    assert group.no_path_count == 2


def test_clear_group_waiting_due_to_congestion_clears_state_but_not_counter():
    group = build_group()

    mark_group_waiting_due_to_congestion(group, frame=10)
    clear_group_waiting_due_to_congestion(group)

    assert group.waiting_due_to_congestion is False
    assert group.waiting_since_frame is None
    assert group.no_path_count == 1


def test_set_group_speed_updates_active_agents_only():
    class FakeAgent:
        def __init__(self, agent_id):
            self.id = agent_id
            self.model = SimpleNamespace(v0=1.0)

    agents_by_id = {
        1: FakeAgent(1),
    }

    simulation = SimpleNamespace(
        agents=lambda: list(agents_by_id.values()),
        agent=lambda agent_id: agents_by_id[agent_id],
    )

    group = AgentGroup(
        agents=[1, 2],
        path=["A", "B"],
        current_nodes={1: "A", 2: "A"},
        algorithm=0,
        awareness_level=0,
    )

    set_group_speed(simulation, group, 0.0)

    assert agents_by_id[1].model.v0 == 0.0