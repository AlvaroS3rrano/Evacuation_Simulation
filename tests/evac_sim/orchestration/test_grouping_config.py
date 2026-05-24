import pytest

from evac_sim.orchestration.grouping_config import (
    GroupDistributionConfig,
    build_group_distribution_config,
)


def test_grouping_config_is_optional():
    assert build_group_distribution_config({}) is None


def test_grouping_config_can_be_disabled():
    cfg = {
        "grouping": {
            "enabled": False,
            "max_group_size": 8,
        }
    }

    assert build_group_distribution_config(cfg) is None


def test_build_fixed_grouping_config_with_defaults():
    cfg = {
        "grouping": {
            "max_group_size": 8,
        }
    }

    grouping_config = build_group_distribution_config(cfg)

    assert grouping_config == GroupDistributionConfig(
        max_group_size=8,
        distribution="fixed",
        min_group_size=1,
        mean_group_size=None,
        std_group_size=None,
        seed=None,
    )


def test_build_normal_grouping_config_with_aliases():
    cfg = {
        "grouping": {
            "enabled": True,
            "max_group_size": 8,
            "min_group_size": 2,
            "distribution": "normal",
            "mean": 5,
            "std": 1.5,
            "seed": 123,
        }
    }

    grouping_config = build_group_distribution_config(cfg)

    assert grouping_config == GroupDistributionConfig(
        max_group_size=8,
        distribution="normal",
        min_group_size=2,
        mean_group_size=5.0,
        std_group_size=1.5,
        seed=123,
    )


def test_build_grouping_config_rejects_non_mapping_grouping():
    with pytest.raises(TypeError, match="grouping must be a mapping"):
        build_group_distribution_config({"grouping": True})


def test_build_grouping_config_requires_max_group_size_when_enabled():
    with pytest.raises(ValueError, match="grouping.max_group_size is required"):
        build_group_distribution_config({"grouping": {"enabled": True}})


def test_build_grouping_config_rejects_invalid_distribution():
    cfg = {
        "grouping": {
            "max_group_size": 8,
            "distribution": "invalid",
        }
    }

    with pytest.raises(ValueError, match="Unsupported grouping.distribution"):
        build_group_distribution_config(cfg)


def test_build_grouping_config_rejects_invalid_size_bounds():
    cfg = {
        "grouping": {
            "max_group_size": 3,
            "min_group_size": 5,
        }
    }

    with pytest.raises(ValueError, match="min_group_size cannot be greater"):
        build_group_distribution_config(cfg)


def test_build_grouping_config_rejects_non_positive_max_group_size():
    cfg = {
        "grouping": {
            "max_group_size": 0,
        }
    }

    with pytest.raises(ValueError, match="max_group_size must be > 0"):
        build_group_distribution_config(cfg)