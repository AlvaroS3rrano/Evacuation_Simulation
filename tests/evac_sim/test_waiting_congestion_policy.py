from evac_sim.core.agent_group import AgentGroup


def test_agent_group_has_waiting_congestion_state_defaults():
    group = AgentGroup(
        agents=[],
        path=None,
        current_nodes={},
        algorithm=0,
        awareness_level=0,
    )

    assert group.waiting_due_to_congestion is False
    assert group.waiting_since_frame is None
    assert group.no_path_count == 0


def test_agent_group_can_store_waiting_congestion_state():
    group = AgentGroup(
        agents=[1, 2],
        path=["A", "B"],
        current_nodes={1: "A", 2: "A"},
        algorithm=0,
        awareness_level=1,
    )

    group.waiting_due_to_congestion = True
    group.waiting_since_frame = 10
    group.no_path_count = 3

    assert group.waiting_due_to_congestion is True
    assert group.waiting_since_frame == 10
    assert group.no_path_count == 3