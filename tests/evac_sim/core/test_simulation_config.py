import pytest

from evac_sim.core.simulation_config import SimulationConfig


def test_simulation_config_uses_default_values():
    config = SimulationConfig()

    assert config.simulation is None
    assert config.every_nth_frame_simulation == 4
    assert config.every_nth_frame_animation == 50
    assert config.waypoints_ids == {}
    assert config.exit_ids == {}
    assert config.gamma == 0.4
    assert config.normal_max_speed == 1.0
    assert config.stairs_max_speed == 0.5


def test_simulation_config_accepts_custom_values():
    config = SimulationConfig(
        simulation="MySimulation",
        every_nth_frame_simulation=5,
        every_nth_frame_animation=20,
        waypoints_ids={"A": 101},
        exit_ids={"exitA": "Node_A"},
        gamma=0.2,
        normal_max_speed=1.2,
        stairs_max_speed=0.7,
    )

    assert config.simulation == "MySimulation"
    assert config.every_nth_frame_simulation == 5
    assert config.every_nth_frame_animation == 20
    assert config.waypoints_ids == {"A": 101}
    assert config.exit_ids == {"exitA": "Node_A"}
    assert config.gamma == 0.2
    assert config.normal_max_speed == 1.2
    assert config.stairs_max_speed == 0.7


def test_simulation_config_uses_independent_dicts():
    config1 = SimulationConfig()
    config2 = SimulationConfig()

    config1.waypoints_ids["A"] = 101
    config1.exit_ids["exitA"] = "Node_A"

    assert config2.waypoints_ids == {}
    assert config2.exit_ids == {}


def test_exit_names_returns_exit_id_keys():
    config = SimulationConfig(exit_ids={"exitA": "Node_A", "exitB": "Node_B"})

    assert config.exit_names == ["exitA", "exitB"]


def test_simulation_config_rejects_non_positive_simulation_frame_interval():
    with pytest.raises(ValueError, match="every_nth_frame_simulation must be > 0"):
        SimulationConfig(every_nth_frame_simulation=0)


def test_simulation_config_rejects_non_positive_animation_frame_interval():
    with pytest.raises(ValueError, match="every_nth_frame_animation must be > 0"):
        SimulationConfig(every_nth_frame_animation=0)


def test_simulation_config_rejects_negative_gamma():
    with pytest.raises(ValueError, match="gamma must be >= 0"):
        SimulationConfig(gamma=-0.1)


def test_simulation_config_rejects_non_positive_normal_max_speed():
    with pytest.raises(ValueError, match="normal_max_speed must be > 0"):
        SimulationConfig(normal_max_speed=0)


def test_simulation_config_rejects_non_positive_stairs_max_speed():
    with pytest.raises(ValueError, match="stairs_max_speed must be > 0"):
        SimulationConfig(stairs_max_speed=0)