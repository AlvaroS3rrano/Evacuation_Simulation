from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation import simulation_manager as sm


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


def build_sim_cfg():
    return SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [SimpleNamespace(id=1), SimpleNamespace(id=2)],
        ),
        every_nth_frame_simulation=1,
        every_nth_frame_animation=1,
        gamma=0.4,
    )


def test_process_frame_calls_process_single_group(monkeypatch):
    captured = []

    monkeypatch.setattr(
        sm,
        "get_risk_levels_by_frame",
        lambda conn, case_name, frame: {"A": 0.1},
    )

    monkeypatch.setattr(
        sm,
        "compute_current_nodes",
        lambda sim_cfg, group, frame: None,
    )

    monkeypatch.setattr(
        sm,
        "split_group_by_progress_threshold",
        lambda group, threshold: None,
    )

    def fake_process_single_group(*args, **kwargs):
        captured.append(
            {
                "case_name": kwargs["case_name"],
                "mode": kwargs["mode"],
                "frame": kwargs["frame"],
                "heuristic": kwargs["heuristic"],
                "horizon_k": kwargs["horizon_k"],
                "no_path_policy": kwargs["no_path_policy"],
                "group_id": kwargs["group_id"],
            }
        )

    monkeypatch.setattr(sm, "process_single_group", fake_process_single_group)

    groups = {"g1": build_group()}

    sm.process_frame(
        build_sim_cfg(),
        groups,
        env_info=SimpleNamespace(graph=None),
        conn=None,
        case_name="case",
        mode=0,
        frame=3,
        threshold=0.5,
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        no_path_policy="wait",
    )

    assert captured == [
        {
            "case_name": "case",
            "mode": 0,
            "frame": 3,
            "heuristic": "h2",
            "horizon_k": 2,
            "no_path_policy": "wait",
            "group_id": "g1",
        }
    ]


def test_process_frame_filters_inactive_agents(monkeypatch):
    captured = []

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sm,
        "split_group_by_progress_threshold",
        lambda group, threshold: None,
    )

    def fake_process_single_group(*args, **kwargs):
        captured.append(kwargs["group"].agents)

    monkeypatch.setattr(sm, "process_single_group", fake_process_single_group)

    sim_cfg = SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [SimpleNamespace(id=1)],
        ),
        gamma=0.4,
    )

    groups = {
        "g1": build_group(
            agents=[1, 2],
            current_nodes={1: "A", 2: "A"},
        )
    }

    sm.process_frame(
        sim_cfg,
        groups,
        env_info=SimpleNamespace(graph=None),
        conn=None,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
    )

    assert captured == [[1]]
    assert groups["g1"].agents == [1]
    assert groups["g1"].current_nodes == {1: "A"}


def test_process_frame_splits_group_and_processes_both_subgroups(monkeypatch):
    processed_group_ids = []

    lead_group = build_group(
        agents=[1],
        current_nodes={1: "B"},
    )
    lag_group = build_group(
        agents=[2],
        current_nodes={2: "A"},
    )

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sm,
        "split_group_by_progress_threshold",
        lambda group, threshold: (lead_group, lag_group),
    )
    monkeypatch.setattr(
        sm,
        "next_split_group_id",
        lambda groups, parent_group_id, suffix="lag": "g1__lag",
    )
    monkeypatch.setattr(
        sm,
        "release_group_reserved_edges",
        lambda *args, **kwargs: None,
    )

    def fake_process_single_group(*args, **kwargs):
        processed_group_ids.append(kwargs["group_id"])

    monkeypatch.setattr(sm, "process_single_group", fake_process_single_group)

    groups = {"g1": build_group()}

    sm.process_frame(
        build_sim_cfg(),
        groups,
        env_info=SimpleNamespace(graph=None),
        conn=None,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
        heuristic="h2",
        group_split_threshold=1,
    )

    assert processed_group_ids == ["g1", "g1__lag"]
    assert groups["g1"] is lead_group
    assert groups["g1__lag"] is lag_group


def test_process_frame_skips_group_when_all_agents_are_inactive(monkeypatch):
    called = False

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)

    def fake_process_single_group(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(sm, "process_single_group", fake_process_single_group)

    sim_cfg = SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [],
        ),
        gamma=0.4,
    )

    groups = {"g1": build_group()}

    sm.process_frame(
        sim_cfg,
        groups,
        env_info=SimpleNamespace(graph=None),
        conn=None,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
    )

    assert called is False
    assert groups["g1"].agents == []


def test_run_agent_simulation_processes_initial_frame(monkeypatch):
    calls = []

    class FakeSimulation:
        def __init__(self):
            self._agent_count = 1

        def agent_count(self):
            return self._agent_count

        def iterate(self):
            self._agent_count = 0

        def iteration_count(self):
            return 1

    sim_cfg = SimpleNamespace(
        simulation=FakeSimulation(),
        every_nth_frame_simulation=1,
        every_nth_frame_animation=1,
        gamma=0.4,
    )

    def fake_process_frame(*args, **kwargs):
        calls.append(kwargs["frame"])

    monkeypatch.setattr(sm, "process_frame", fake_process_frame)

    sm.run_agent_simulation(
        sim_cfg,
        log_every_frames=1,
        agent_groups={"g1": build_group()},
        env_info=SimpleNamespace(graph=None),
        conn=None,
        case_name="case",
        mode=0,
        threshold=0.5,
    )

    assert calls == [0, 1]


def test_set_agents_in_simulation_adds_agents():
    added_params = []

    class FakeSimulation:
        def add_agent(self, params):
            added_params.append(params)
            return SimpleNamespace(id=len(added_params))

    agents = sm.set_agents_in_simulation(
        FakeSimulation(),
        positions=[(1.0, 2.0), (3.0, 4.0)],
        journey_id=10,
        waypoint_id=20,
        speed=1.5,
    )

    assert [agent.id for agent in agents] == [1, 2]
    assert len(added_params) == 2
    assert added_params[0].journey_id == 10
    assert added_params[0].stage_id == 20
    assert added_params[0].desired_speed == 1.5