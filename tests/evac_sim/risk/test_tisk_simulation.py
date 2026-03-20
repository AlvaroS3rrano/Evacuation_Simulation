import networkx as nx
import pytest

from evac_sim.risk.risk_simulation import simulate_risk


class DummyRiskValues:
    def __init__(
        self,
        iterations,
        increase_chance,
        propagation_threshold,
        starting_risks=None,
        risk_overrides=None,
    ):
        self.iterations = iterations
        self.increase_chance = increase_chance
        self.propagation_threshold = propagation_threshold
        self.starting_risks = starting_risks or []
        self.risk_overrides = risk_overrides or []


def make_graph():
    g = nx.DiGraph()
    for node in ["A", "B", "C", "EXIT"]:
        g.add_node(node, risk=0.0)
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    g.add_edge("C", "EXIT")
    return g


def collect_written_frames(monkeypatch):
    written = {}

    def fake_write_risk_levels(connection, frame, risks):
        written[frame] = dict(risks)

    monkeypatch.setattr(
        "evac_sim.risk.risk_simulation.write_risk_levels",
        fake_write_risk_levels,
    )
    return written


def test_simulate_risk_applies_starting_risks_at_frame_zero(monkeypatch):
    g = make_graph()
    written = collect_written_frames(monkeypatch)

    values = DummyRiskValues(
        iterations=3,
        increase_chance=0.0,
        propagation_threshold=0.5,
        starting_risks=[("A", 0.8), ("B", 0.2)],
    )

    simulate_risk(
        risk_sim_values=values,
        every_nth_frame=1,
        G=g,
        exits=["EXIT"],
        connection=None,
        seed=123,
    )

    assert 0 in written
    assert written[0]["A"] == 0.8
    assert written[0]["B"] == 0.2
    assert written[0]["EXIT"] == 0.0


def test_exit_nodes_remain_zero(monkeypatch):
    g = make_graph()
    written = collect_written_frames(monkeypatch)

    values = DummyRiskValues(
        iterations=5,
        increase_chance=1.0,
        propagation_threshold=0.1,
        starting_risks=[("A", 1.0), ("EXIT", 0.9)],
    )

    simulate_risk(
        risk_sim_values=values,
        every_nth_frame=1,
        G=g,
        exits=["EXIT"],
        connection=None,
        seed=123,
    )

    for frame, risks in written.items():
        assert risks["EXIT"] == 0.0, f"EXIT should remain 0 at frame {frame}"


def test_simulate_risk_is_reproducible_with_same_seed(monkeypatch):
    written_1 = {}
    written_2 = {}

    def fake_write_1(connection, frame, risks):
        written_1[frame] = dict(risks)

    def fake_write_2(connection, frame, risks):
        written_2[frame] = dict(risks)

    values = DummyRiskValues(
        iterations=5,
        increase_chance=0.8,
        propagation_threshold=0.3,
        starting_risks=[("A", 0.7)],
    )

    g1 = make_graph()
    monkeypatch.setattr("evac_sim.risk.risk_simulation.write_risk_levels", fake_write_1)
    simulate_risk(values, 1, g1, ["EXIT"], None, seed=999)

    g2 = make_graph()
    monkeypatch.setattr("evac_sim.risk.risk_simulation.write_risk_levels", fake_write_2)
    simulate_risk(values, 1, g2, ["EXIT"], None, seed=999)

    assert written_1 == written_2


def test_risk_override_applies_on_target_frame(monkeypatch):
    g = make_graph()
    written = collect_written_frames(monkeypatch)

    values = DummyRiskValues(
        iterations=3,
        increase_chance=0.0,
        propagation_threshold=0.9,
        starting_risks=[("A", 0.2)],
        risk_overrides=[(2, "B", 0.9)],
    )

    simulate_risk(
        risk_sim_values=values,
        every_nth_frame=1,
        G=g,
        exits=["EXIT"],
        connection=None,
        seed=1,
    )

    assert written[2]["B"] == 0.9


def test_iterations_must_be_positive():
    g = make_graph()
    values = DummyRiskValues(
        iterations=0,
        increase_chance=0.0,
        propagation_threshold=0.5,
    )

    with pytest.raises(ValueError, match="iterations must be"):
        simulate_risk(values, 1, g, ["EXIT"], None, seed=1)


def test_every_nth_frame_must_be_positive():
    g = make_graph()
    values = DummyRiskValues(
        iterations=3,
        increase_chance=0.0,
        propagation_threshold=0.5,
    )

    with pytest.raises(ValueError, match="every_nth_frame must be"):
        simulate_risk(values, 0, g, ["EXIT"], None, seed=1)

def test_different_seed_changes_evolution(monkeypatch):
    values = DummyRiskValues(
        iterations=5,
        increase_chance=0.9,
        propagation_threshold=0.3,
        starting_risks=[("A", 0.8)],
    )

    out1 = {}
    out2 = {}

    def fake_write_1(connection, frame, risks):
        out1[frame] = dict(risks)

    def fake_write_2(connection, frame, risks):
        out2[frame] = dict(risks)

    g1 = make_graph()
    monkeypatch.setattr("evac_sim.risk.risk_simulation.write_risk_levels", fake_write_1)
    simulate_risk(values, 1, g1, ["EXIT"], None, seed=111)

    g2 = make_graph()
    monkeypatch.setattr("evac_sim.risk.risk_simulation.write_risk_levels", fake_write_2)
    simulate_risk(values, 1, g2, ["EXIT"], None, seed=222)

    assert out1 != out2