from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation.group_splitting import (
    next_split_group_id,
    split_group_by_progress_threshold,
)


def build_group(
    awareness_level=0,
    path=None,
    current_nodes=None,
    agents=None,
):
    if path is None:
        path = ["A", "B", "C"]

    if current_nodes is None:
        current_nodes = {1: "A", 2: "A"}

    if agents is None:
        agents = [1, 2]

    return AgentGroup(
        agents=agents,
        path=path,
        current_nodes=current_nodes,
        algorithm=0,
        awareness_level=awareness_level,
        initial_agents_ids=list(agents),
    )


def test_next_split_group_id_returns_default_lag_id():
    assert next_split_group_id({"g1": object()}, "g1") == "g1__lag"


def test_next_split_group_id_increments_when_candidate_exists():
    groups = {
        "g1": object(),
        "g1__lag": object(),
        "g1__lag_2": object(),
    }

    assert next_split_group_id(groups, "g1") == "g1__lag_3"


def test_split_group_by_progress_threshold_splits_lagging_agents():
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D", "E"],
        current_nodes={1: "D", 2: "D", 3: "B", 4: "A"},
        agents=[1, 2, 3, 4],
    )

    result = split_group_by_progress_threshold(group, threshold=1)

    assert result is not None

    lead_group, lag_group = result

    assert lead_group.agents == [1, 2]
    assert lag_group.agents == [3, 4]
    assert lead_group.path == ["A", "B", "C", "D", "E"]
    assert lag_group.path == ["A", "B", "C", "D", "E"]


def test_split_group_by_progress_threshold_returns_none_when_dispersion_is_within_threshold():
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "C", 2: "B", 3: "B"},
        agents=[1, 2, 3],
    )

    result = split_group_by_progress_threshold(group, threshold=1)

    assert result is None


def test_split_group_by_progress_threshold_returns_none_when_threshold_is_none():
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "C", 2: "A"},
        agents=[1, 2],
    )

    result = split_group_by_progress_threshold(group, threshold=None)

    assert result is None


def test_split_group_by_progress_threshold_does_not_split_waiting_group():
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "D", 2: "A"},
        agents=[1, 2],
    )
    group.waiting_due_to_congestion = True

    result = split_group_by_progress_threshold(group, threshold=1)

    assert result is None