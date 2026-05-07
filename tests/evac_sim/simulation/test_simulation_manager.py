from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation import simulation_manager as sm


def build_group(awareness_level=0, path=None, current_nodes=None, agents=None):
    if path is None:
        path = ["A", "B", "C"]
    if current_nodes is None:
        current_nodes = {1: "A", 2: "A"}
    if agents is None:
        agents = [1, 2]

    group = AgentGroup(
        agents=agents,
        path=path,
        current_nodes=current_nodes,
        algorithm=0,
        awareness_level=awareness_level,
    )
    group.reserved_edges = set()
    group.reserved_group_size = 0
    group.initial_agents_ids = list(agents)
    return group


def build_sim_cfg():
    return SimpleNamespace(
        simulation=SimpleNamespace(
            agents=lambda: [SimpleNamespace(id=1), SimpleNamespace(id=2)],
            switch_agent_journey=lambda *args, **kwargs: None,
        ),
        waypoints_ids={"B": 101, "C": 102, "D": 103, "X": 104, "Y": 105},
        exit_ids={"D": 201, "Y": 202},
        exit_names=["D", "Y"],
        gamma=0.4,
    )


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


def test_update_group_paths_passes_horizon_k_to_effective_cost(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(sm, "compute_alternative_path", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )

    monkeypatch.setattr(
        sm,
        "_remaining_path_from_node",
        lambda path, current_node: path,
    )

    captured_horizons = []

    def fake_compute_path_effective_cost(graph, path, **kwargs):
        captured_horizons.append(kwargs.get("horizon_k"))

        costs = {
            tuple(["A", "B", "C", "D"]): 10.0,
            tuple(["A", "X", "Y"]): 7.0,
        }
        return costs[tuple(path)]

    monkeypatch.setattr(
        sm,
        "compute_path_effective_cost",
        fake_compute_path_effective_cost,
    )

    monkeypatch.setattr(
        sm,
        "set_journeys",
        lambda simulation, curr_node, paths, waypoints, exit_ids: {
            curr_node: [(999, paths[0])]
        },
    )

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert captured_horizons == [2, 2]
    assert updated_group.path == ["A", "X", "Y"]


def test_high_awareness_reroutes_due_to_congestion_improvement(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: False)

    monkeypatch.setattr(sm, "compute_alternative_path", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )

    costs = {
        tuple(["A", "B", "C", "D"]): 10.0,
        tuple(["A", "X", "Y"]): 7.0,
    }

    monkeypatch.setattr(
        sm,
        "_remaining_path_from_node",
        lambda path, current_node: path,
    )

    monkeypatch.setattr(
        sm,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: costs[tuple(path)],
    )

    monkeypatch.setattr(
        sm,
        "set_journeys",
        lambda simulation, curr_node, paths, waypoints, exit_ids: {
            curr_node: [(999, paths[0])]
        },
    )

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert updated_group.path == ["A", "X", "Y"]


def test_high_awareness_does_not_reroute_if_improvement_is_below_epsilon(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: False)

    monkeypatch.setattr(sm, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )

    # 5% improvement, lower than 10%
    costs = {
        tuple(["A", "B", "C", "D"]): 10.0,
        tuple(["A", "X", "Y"]): 9.5,
    }

    monkeypatch.setattr(sm, "_remaining_path_from_node", lambda path, current_node: path)
    monkeypatch.setattr(
        sm,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: costs[tuple(path)],
    )

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert updated_group.path == ["A", "B", "C", "D"]


def test_low_awareness_does_not_reroute_due_to_congestion_only(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=0,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: False)

    # No risk trigger
    monkeypatch.setattr(sm, "compute_alternative_path", lambda *args, **kwargs: None)

    # Even with a better option low awareness should not change
    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )

    monkeypatch.setattr(sm, "_remaining_path_from_node", lambda path, current_node: path)
    monkeypatch.setattr(
        sm,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: 1.0,
    )

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert updated_group.path == ["A", "B", "C", "D"]


def test_high_awareness_still_reroutes_due_to_risk_trigger(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: False)

    # Risk trigger
    monkeypatch.setattr(
        sm,
        "compute_alternative_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )

    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        sm,
        "set_journeys",
        lambda simulation, curr_node, paths, waypoints, exit_ids: {
            curr_node: [(999, paths[0])]
        },
    )

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={"C": 0.9},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert updated_group.path == ["A", "X", "Y"]


def test_high_awareness_does_not_reroute_if_best_path_is_equivalent(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(sm, "validate_agent", lambda *args, **kwargs: True)

    monkeypatch.setattr(sm, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sm,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "B", "C", "D"],
    )

    monkeypatch.setattr(sm, "is_sublist", lambda alt, current: True)

    updated_group = sm.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=0,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        congestion_reroute_epsilon=0.10,
    )

    assert updated_group.path == ["A", "B", "C", "D"]


def test_process_frame_releases_own_reservations_before_reroute_evaluation(monkeypatch):
    order = []

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "record_group_path_data", lambda *args, **kwargs: None)

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        order.append(("reserve", tuple(group.path), kwargs.get("horizon_k")))

    monkeypatch.setattr(sm, "update_group_reserved_edges", fake_update_group_reserved_edges)
    monkeypatch.setattr(
        sm,
        "release_group_reserved_edges",
        lambda *args, **kwargs: order.append(("release", None, None)),
    )
    monkeypatch.setattr(
        sm,
        "restore_group_reserved_edges",
        lambda *args, **kwargs: order.append(("restore", None, None)),
    )

    monkeypatch.setattr(
        sm,
        "update_group_paths",
        lambda *args, **kwargs: args[2],  # no path change
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

    assert order == [
        ("reserve", ("A", "B", "C"), 2),
        ("release", None, None),
        ("restore", None, None),
    ]


def test_process_frame_restores_previous_reservations_when_path_does_not_change(monkeypatch):
    order = []

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "record_group_path_data", lambda *args, **kwargs: None)

    monkeypatch.setattr(
        sm,
        "update_group_reserved_edges",
        lambda *args, **kwargs: order.append("reserve"),
    )
    monkeypatch.setattr(
        sm,
        "release_group_reserved_edges",
        lambda *args, **kwargs: order.append("release"),
    )
    monkeypatch.setattr(
        sm,
        "restore_group_reserved_edges",
        lambda *args, **kwargs: order.append("restore"),
    )

    monkeypatch.setattr(
        sm,
        "update_group_paths",
        lambda *args, **kwargs: args[2],  # no reroute
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

    assert order == ["reserve", "release", "restore"]


def test_process_frame_replaces_old_reservations_when_path_changes(monkeypatch):
    order = []

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "record_group_path_data", lambda *args, **kwargs: None)

    def fake_update_group_reserved_edges(env_info, group, **kwargs):
        order.append(("reserve", tuple(group.path), kwargs.get("horizon_k")))

    monkeypatch.setattr(sm, "update_group_reserved_edges", fake_update_group_reserved_edges)
    monkeypatch.setattr(
        sm,
        "release_group_reserved_edges",
        lambda *args, **kwargs: order.append(("release", None, None)),
    )
    monkeypatch.setattr(
        sm,
        "restore_group_reserved_edges",
        lambda *args, **kwargs: order.append(("restore", None, None)),
    )

    def fake_update_group_paths(*args, **kwargs):
        group = args[2]
        group.path = ["A", "X", "D"]
        return group

    monkeypatch.setattr(sm, "update_group_paths", fake_update_group_paths)

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

    assert order == [
        ("reserve", ("A", "B", "C"), 2),
        ("release", None, None),
        ("reserve", ("A", "X", "D"), 2),
    ]


def test_process_frame_does_not_restore_old_reservations_after_reroute(monkeypatch):
    calls = {"restore": 0}

    monkeypatch.setattr(sm, "get_risk_levels_by_frame", lambda *args, **kwargs: {})
    monkeypatch.setattr(sm, "compute_current_nodes", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "insert_agent_areas", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "update_agent_speed_on_stairs", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "record_group_path_data", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "update_group_reserved_edges", lambda *args, **kwargs: None)
    monkeypatch.setattr(sm, "release_group_reserved_edges", lambda *args, **kwargs: None)

    def fake_restore_group_reserved_edges(*args, **kwargs):
        calls["restore"] += 1

    monkeypatch.setattr(sm, "restore_group_reserved_edges", fake_restore_group_reserved_edges)

    def fake_update_group_paths(*args, **kwargs):
        group = args[2]
        group.path = ["A", "X", "D"]
        return group

    monkeypatch.setattr(sm, "update_group_paths", fake_update_group_paths)

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

    assert calls["restore"] == 0


def test_split_group_by_progress_threshold_splits_lagging_agents():
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D", "E"],
        current_nodes={1: "D", 2: "D", 3: "B", 4: "A"},
        agents=[1, 2, 3, 4],
    )

    result = sm.split_group_by_progress_threshold(group, threshold=1)

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

    result = sm.split_group_by_progress_threshold(group, threshold=1)

    assert result is None