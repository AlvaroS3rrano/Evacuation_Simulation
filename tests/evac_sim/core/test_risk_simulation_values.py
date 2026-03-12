import pytest

from evac_sim.core.risk_simulation_values import RiskSimulationValues


def test_risk_simulation_values_uses_defaults():
    values = RiskSimulationValues()

    assert values.iterations == 3000
    assert values.increase_chance == 0.01
    assert values.propagation_threshold == 0.5
    assert values.starting_risks == []
    assert values.risk_overrides == []


def test_risk_simulation_values_accepts_custom_values():
    values = RiskSimulationValues(
        iterations=1000,
        increase_chance=0.05,
        propagation_threshold=0.7,
        starting_risks=[("A", 0.2), ("B", 0.4)],
        risk_overrides=[(10, "A", 0.8)],
    )

    assert values.iterations == 1000
    assert values.increase_chance == 0.05
    assert values.propagation_threshold == 0.7
    assert values.starting_risks == [("A", 0.2), ("B", 0.4)]
    assert values.risk_overrides == [(10, "A", 0.8)]


def test_risk_simulation_values_uses_independent_lists():
    values1 = RiskSimulationValues()
    values2 = RiskSimulationValues()

    values1.starting_risks.append(("A", 0.3))
    values1.risk_overrides.append((5, "B", 0.7))

    assert values2.starting_risks == []
    assert values2.risk_overrides == []


def test_risk_simulation_values_rejects_non_positive_iterations():
    with pytest.raises(ValueError, match="iterations must be > 0"):
        RiskSimulationValues(iterations=0)


def test_risk_simulation_values_rejects_invalid_increase_chance():
    with pytest.raises(ValueError, match="increase_chance must be between 0 and 1"):
        RiskSimulationValues(increase_chance=1.5)


def test_risk_simulation_values_rejects_invalid_propagation_threshold():
    with pytest.raises(ValueError, match="propagation_threshold must be between 0 and 1"):
        RiskSimulationValues(propagation_threshold=-0.1)