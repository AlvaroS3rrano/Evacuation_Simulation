from types import SimpleNamespace

from evac_sim.core.agent_group import AgentGroup
from evac_sim.simulation import group_path_updates as gpu


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
            switch_agent_journey=lambda *args, **kwargs: None,
        ),
        waypoints_ids={"B": 101, "C": 102, "D": 103, "X": 104, "Y": 105},
        exit_ids={"D": 201, "Y": 202},
        exit_names=["D", "Y"],
        gamma=0.4,
    )


def test_update_group_paths_passes_horizon_k_to_effective_cost(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(gpu, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )
    monkeypatch.setattr(
        gpu,
        "remaining_path_from_node",
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
        gpu,
        "compute_path_effective_cost",
        fake_compute_path_effective_cost,
    )

    monkeypatch.setattr(
        gpu,
        "apply_group_path",
        lambda sim_cfg, group, current_node, full_path: setattr(group, "path", full_path),
    )

    updated_group = gpu.update_group_paths(
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

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(gpu, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )
    monkeypatch.setattr(gpu, "remaining_path_from_node", lambda path, current_node: path)
    monkeypatch.setattr(
        gpu,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: {
            tuple(["A", "B", "C", "D"]): 10.0,
            tuple(["A", "X", "Y"]): 7.0,
        }[tuple(path)],
    )
    monkeypatch.setattr(
        gpu,
        "apply_group_path",
        lambda sim_cfg, group, current_node, full_path: setattr(group, "path", full_path),
    )

    updated_group = gpu.update_group_paths(
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

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(gpu, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )
    monkeypatch.setattr(gpu, "remaining_path_from_node", lambda path, current_node: path)
    monkeypatch.setattr(
        gpu,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: {
            tuple(["A", "B", "C", "D"]): 10.0,
            tuple(["A", "X", "Y"]): 9.5,
        }[tuple(path)],
    )

    updated_group = gpu.update_group_paths(
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

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(gpu, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )
    monkeypatch.setattr(gpu, "remaining_path_from_node", lambda path, current_node: path)
    monkeypatch.setattr(
        gpu,
        "compute_path_effective_cost",
        lambda graph, path, **kwargs: 1.0,
    )

    updated_group = gpu.update_group_paths(
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

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: False)
    monkeypatch.setattr(
        gpu,
        "compute_alternative_path",
        lambda *args, **kwargs: ["A", "X", "Y"],
    )
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        gpu,
        "apply_group_path",
        lambda sim_cfg, group, current_node, full_path: setattr(group, "path", full_path),
    )

    updated_group = gpu.update_group_paths(
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

    monkeypatch.setattr(gpu, "validate_agent", lambda *args, **kwargs: True)
    monkeypatch.setattr(gpu, "compute_alternative_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: ["A", "B", "C", "D"],
    )
    monkeypatch.setattr(gpu, "is_sublist", lambda alt, current: True)

    updated_group = gpu.update_group_paths(
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


def test_waiting_group_keeps_waiting_when_no_path_exists(monkeypatch):
    sim_cfg = build_sim_cfg()
    env_info = SimpleNamespace(graph={})
    group = build_group(
        awareness_level=1,
        path=["A", "B", "C", "D"],
        current_nodes={1: "A", 2: "A"},
        agents=[1, 2],
    )
    group.waiting_due_to_congestion = True

    monkeypatch.setattr(
        gpu,
        "compute_best_available_path",
        lambda *args, **kwargs: None,
    )

    updated_group = gpu.update_group_paths(
        sim_cfg,
        risk_map={},
        group=group,
        env_info=env_info,
        threshold=0.5,
        frame=5,
        group_id="g1",
        heuristic="h2",
        beta=1.0,
        horizon_k=2,
        no_path_policy="wait",
    )

    assert updated_group.waiting_due_to_congestion is True
    assert updated_group.waiting_since_frame == 5
    assert updated_group.no_path_count == 1