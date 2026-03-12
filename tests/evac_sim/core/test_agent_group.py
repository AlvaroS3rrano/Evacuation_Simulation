import pytest

from evac_sim.core.agent_group import AgentGroup


def test_agent_group_creation():
    group = AgentGroup(
        agents=[1, 2, 3],
        path=["A", "B", "C"],
        current_nodes={1: "A", 2: "A", 3: "B"},
        algorithm=0,
        awareness_level=1,
    )

    assert group.agents == [1, 2, 3]
    assert group.path == ["A", "B", "C"]
    assert group.current_nodes == {1: "A", 2: "A", 3: "B"}
    assert group.algorithm == 0
    assert group.awareness_level == 1
    assert group.blocked_nodes == []
    assert group.wait_until_node is None
    assert group.agents_in_stairs == []
    assert group.initial_agents_ids == []


def test_agent_group_accepts_optional_values():
    group = AgentGroup(
        agents=[1],
        path=["A", "B"],
        current_nodes={1: "A"},
        algorithm=1,
        awareness_level=0,
        blocked_nodes=["X"],
        wait_until_node="B",
        agents_in_stairs=[1],
        initial_agents_ids=[1],
    )

    assert group.blocked_nodes == ["X"]
    assert group.wait_until_node == "B"
    assert group.agents_in_stairs == [1]
    assert group.initial_agents_ids == [1]


def test_agent_group_uses_independent_default_lists():
    group1 = AgentGroup(
        agents=[1],
        path=["A"],
        current_nodes={1: "A"},
        algorithm=0,
        awareness_level=0,
    )
    group2 = AgentGroup(
        agents=[2],
        path=["B"],
        current_nodes={2: "B"},
        algorithm=0,
        awareness_level=0,
    )

    group1.blocked_nodes.append("X")
    group1.agents_in_stairs.append(1)

    assert group2.blocked_nodes == []
    assert group2.agents_in_stairs == []


def test_agent_group_rejects_invalid_algorithm():
    with pytest.raises(ValueError, match="algorithm must be 0"):
        AgentGroup(
            agents=[1],
            path=["A"],
            current_nodes={1: "A"},
            algorithm=2,
            awareness_level=0,
        )


def test_agent_group_rejects_invalid_awareness_level():
    with pytest.raises(ValueError, match="awareness_level must be 0 or 1"):
        AgentGroup(
            agents=[1],
            path=["A"],
            current_nodes={1: "A"},
            algorithm=0,
            awareness_level=3,
        )