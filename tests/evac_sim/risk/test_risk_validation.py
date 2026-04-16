import networkx as nx
import pytest

from evac_sim.risk.risk_validation import validate_risk_inputs


def make_graph():
    g = nx.DiGraph()
    for node in ["A", "B", "EXIT"]:
        g.add_node(node, risk=0.0)
    g.add_edge("A", "B")
    g.add_edge("B", "EXIT")
    return g


def test_invalid_increase_chance_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="increase_chance"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=1.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[],
            risk_overrides=[],
        )


def test_invalid_propagation_threshold_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="propagation_threshold"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=-0.1,
            risk_threshold=0.5,
            starting_risks=[],
            risk_overrides=[],
        )


def test_invalid_risk_threshold_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="risk_threshold"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=2.0,
            starting_risks=[],
            risk_overrides=[],
        )


def test_unknown_starting_risk_node_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="starting_risks"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[("X", 0.4)],
            risk_overrides=[],
        )


def test_unknown_override_node_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="risk_overrides"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[],
            risk_overrides=[(3, "X", 0.7)],
        )


def test_invalid_starting_risk_value_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="starting risk"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[("A", 1.4)],
            risk_overrides=[],
        )


def test_invalid_override_risk_value_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="risk override"):
        validate_risk_inputs(
            graph=g,
            exits=["EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[],
            risk_overrides=[(3, "A", -0.2)],
        )


def test_unknown_exit_raises():
    g = make_graph()
    with pytest.raises(ValueError, match="Exit node"):
        validate_risk_inputs(
            graph=g,
            exits=["MISSING_EXIT"],
            risk_iterations=10,
            every_nth_frame=1,
            increase_chance=0.2,
            propagation_threshold=0.5,
            risk_threshold=0.5,
            starting_risks=[],
            risk_overrides=[],
        )