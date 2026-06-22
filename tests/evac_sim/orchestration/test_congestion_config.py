import pytest

from evac_sim.orchestration.congestion_config import (
    CongestionConfig,
    build_congestion_config,
)


def test_congestion_config_uses_backward_compatible_defaults_when_missing():
    assert build_congestion_config({}) == CongestionConfig(
        edge_capacity_multiplier=1.0,
        use_linear_congestion_cost=False,
        block_edges_at_capacity=False,
    )


def test_congestion_config_enables_linear_policy_when_section_exists():
    cfg = {
        "congestion": {
            "edge_capacity_multiplier": 2.0,
        }
    }

    assert build_congestion_config(cfg) == CongestionConfig(
        edge_capacity_multiplier=2.0,
        use_linear_congestion_cost=True,
        block_edges_at_capacity=True,
        no_path_policy="wait",
    )


def test_congestion_config_can_disable_linear_policy():
    cfg = {
        "congestion": {
            "edge_capacity_multiplier": 2.0,
            "use_linear_congestion_cost": False,
            "block_edges_at_capacity": False,
            "no_path_policy": "raise",
        }
    }

    assert build_congestion_config(cfg) == CongestionConfig(
        edge_capacity_multiplier=2.0,
        use_linear_congestion_cost=False,
        block_edges_at_capacity=False,
        no_path_policy="raise",
    )


def test_congestion_config_rejects_non_mapping_section():
    with pytest.raises(TypeError, match="congestion must be a mapping"):
        build_congestion_config({"congestion": True})


def test_congestion_config_rejects_zero_multiplier():
    cfg = {
        "congestion": {
            "edge_capacity_multiplier": 0,
        }
    }

    with pytest.raises(ValueError, match="edge_capacity_multiplier must be > 0"):
        build_congestion_config(cfg)


def test_congestion_config_rejects_negative_multiplier():
    cfg = {
        "congestion": {
            "edge_capacity_multiplier": -1,
        }
    }

    with pytest.raises(ValueError, match="edge_capacity_multiplier must be > 0"):
        build_congestion_config(cfg)

def test_congestion_config_defaults_to_wait_policy_when_section_exists():
    cfg = {
        "congestion": {
            "edge_capacity_multiplier": 2.0,
        }
    }

    congestion_config = build_congestion_config(cfg)

    assert congestion_config.no_path_policy == "wait"


def test_congestion_config_rejects_invalid_no_path_policy():
    cfg = {
        "congestion": {
            "no_path_policy": "invalid",
        }
    }

    with pytest.raises(ValueError, match="Unsupported congestion.no_path_policy"):
        build_congestion_config(cfg)