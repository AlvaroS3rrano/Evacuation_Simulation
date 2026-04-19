from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation import simulation_manager as sm


def build_group():
    group = AgentGroup(
        agents=[1, 2],
        path=["A", "B", "C"],
        current_nodes={1: "A", 2: "A"},
        algorithm=0,
        awareness_level=0,
    )
    group.reserved_edges = set()
    group.reserved_group_size = 0
    group.initial_agents_ids = [1, 2]
    return group


def test_reservation_horizon_for_heuristic_h1_returns_none():
    assert sm._reservation_horizon_for_heuristic("h1", 5) is None


def test_reservation_horizon_for_heuristic_h2_uses_default_when_missing():
    assert sm._reservation_horizon_for_heuristic("h2", None) == 3


def test_reservation_horizon_for_heuristic_h2_uses_explicit_value():
    assert sm._reservation_horizon_for_heuristic("h2", 7) == 7


def test_process_frame_passes_horizon_to_reservation_updates(monkeypatch):
    captured = []

    monkeypatch.setattr(
        sm,
        "get_risk_levels_by_frame",
        lambda conn, case_name, frame: {},
    )

    monkeypatch.setattr(
        sm,
        "compute_current_nodes",
        lambda sim_cfg, group, frame: None,
    )

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        captured.append(kwargs.get("horizon_k"))

    monkeypatch.setattr(sm, "update_group_reserved_edges", fake_update_group_reserved_edges)

    monkeypatch.setattr(
        sm,
        "insert_agent_areas",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        sm,
        "update_agent_speed_on_stairs",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        sm,
        "update_group_paths",
        lambda *args, **kwargs: args[2],
    )

    monkeypatch.setattr(
        sm,
        "record_group_path_data",
        lambda *args, **kwargs: None,
    )

    sim_cfg = SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [SimpleNamespace(id=1), SimpleNamespace(id=2)]
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
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
    )

    assert captured == [2]


def test_process_frame_reapplies_reservation_after_reroute(monkeypatch):
    captured = []

    monkeypatch.setattr(
        sm,
        "get_risk_levels_by_frame",
        lambda conn, case_name, frame: {},
    )

    monkeypatch.setattr(
        sm,
        "compute_current_nodes",
        lambda sim_cfg, group, frame: None,
    )

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        captured.append((tuple(group.path), kwargs.get("horizon_k")))

    monkeypatch.setattr(sm, "update_group_reserved_edges", fake_update_group_reserved_edges)

    monkeypatch.setattr(
        sm,
        "insert_agent_areas",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        sm,
        "update_agent_speed_on_stairs",
        lambda *args, **kwargs: None,
    )

    def fake_update_group_paths(*args, **kwargs):
        group = args[2]
        group.path = ["A", "X", "D"]
        return group

    monkeypatch.setattr(sm, "update_group_paths", fake_update_group_paths)

    monkeypatch.setattr(
        sm,
        "record_group_path_data",
        lambda *args, **kwargs: None,
    )

    sim_cfg = SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [SimpleNamespace(id=1), SimpleNamespace(id=2)]
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
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
    )

    assert captured[0] == (("A", "B", "C"), 2)
    assert captured[1] == (("A", "X", "D"), 2)
    assert len(captured) == 2