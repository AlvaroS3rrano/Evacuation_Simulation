from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation import group_processing as gp


def build_group(path=None):
    if path is None:
        path = ["A", "B", "C"]

    group = AgentGroup(
        agents=[1, 2],
        path=path,
        current_nodes={1: "A", 2: "A"},
        algorithm=0,
        awareness_level=0,
        initial_agents_ids=[1, 2],
    )
    group.reserved_nodes = set()
    return group


def test_process_single_group_passes_horizon_to_reservation_updates(monkeypatch):
    captured = []

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        captured.append(kwargs.get("horizon_k"))

    monkeypatch.setattr(gp, "update_group_reserved_edges", fake_update_group_reserved_edges)
    monkeypatch.setattr(gp, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "release_group_reserved_edges", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "restore_group_reserved_edges", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "record_group_path_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "update_group_paths", lambda *args, **kwargs: args[2])

    groups = {"g1": build_group()}
    group = groups["g1"]

    gp.process_single_group(
        sim_cfg=SimpleNamespace(simulation=None),
        env_info=SimpleNamespace(graph=None),
        conn=None,
        risks={},
        groups=groups,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.1,
        no_path_policy="raise",
        group_id="g1",
        group=group,
    )

    assert captured == [2]


def test_process_single_group_reapplies_reservation_after_reroute(monkeypatch):
    captured = []

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        captured.append((tuple(group.path), kwargs.get("horizon_k")))

    def fake_update_group_paths(*args, **kwargs):
        group = args[2]
        group.path = ["A", "X", "D"]
        return group

    monkeypatch.setattr(gp, "update_group_reserved_edges", fake_update_group_reserved_edges)
    monkeypatch.setattr(gp, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "release_group_reserved_edges", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "restore_group_reserved_edges", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "record_group_path_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "update_group_paths", fake_update_group_paths)

    groups = {"g1": build_group()}

    gp.process_single_group(
        sim_cfg=SimpleNamespace(simulation=None),
        env_info=SimpleNamespace(graph=None),
        conn=None,
        risks={},
        groups=groups,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.1,
        no_path_policy="raise",
        group_id="g1",
        group=groups["g1"],
    )

    assert captured == [
        (("A", "B", "C"), 2),
        (("A", "X", "D"), 2),
    ]


def test_process_single_group_restores_previous_reservations_when_path_does_not_change(monkeypatch):
    order = []

    monkeypatch.setattr(gp, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "record_group_path_data", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        gp,
        "update_group_reserved_edges",
        lambda *args, **kwargs: order.append("reserve"),
    )
    monkeypatch.setattr(
        gp,
        "release_group_reserved_edges",
        lambda *args, **kwargs: order.append("release"),
    )
    monkeypatch.setattr(
        gp,
        "restore_group_reserved_edges",
        lambda *args, **kwargs: order.append("restore"),
    )
    monkeypatch.setattr(gp, "update_group_paths", lambda *args, **kwargs: args[2])

    groups = {"g1": build_group()}

    gp.process_single_group(
        sim_cfg=SimpleNamespace(simulation=None),
        env_info=SimpleNamespace(graph=None),
        conn=None,
        risks={},
        groups=groups,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.1,
        no_path_policy="raise",
        group_id="g1",
        group=groups["g1"],
    )

    assert order == ["reserve", "restore"]


def test_process_single_group_does_not_reserve_when_group_is_waiting(monkeypatch):
    calls = []

    group = build_group()
    group.waiting_due_to_congestion = True

    monkeypatch.setattr(gp, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "record_group_path_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(gp, "set_group_speed", lambda *args, **kwargs: calls.append("speed"))
    monkeypatch.setattr(gp, "update_group_reserved_edges", lambda *args, **kwargs: calls.append("reserve"))
    monkeypatch.setattr(gp, "release_group_reserved_edges", lambda *args, **kwargs: calls.append("release"))
    monkeypatch.setattr(gp, "restore_group_reserved_edges", lambda *args, **kwargs: calls.append("restore"))
    monkeypatch.setattr(gp, "update_group_paths", lambda *args, **kwargs: args[2])

    groups = {"g1": group}

    gp.process_single_group(
        sim_cfg=SimpleNamespace(simulation=None),
        env_info=SimpleNamespace(graph=None),
        conn=None,
        risks={},
        groups=groups,
        case_name="case",
        mode=0,
        frame=0,
        threshold=0.5,
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.1,
        no_path_policy="wait",
        group_id="g1",
        group=group,
    )

    assert calls == ["speed"]