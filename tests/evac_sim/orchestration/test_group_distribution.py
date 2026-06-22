import numpy as np

from evac_sim.orchestration.group_distribution import build_group_position_batches
from evac_sim.orchestration.grouping_config import GroupDistributionConfig


def test_build_group_position_batches_preserves_old_behavior_when_config_is_none():
    positions = {
        "1": np.array([[0.0, 0.0], [1.0, 1.0]]),
        "2": np.array([[2.0, 2.0], [3.0, 3.0], [4.0, 4.0]]),
    }

    batches = build_group_position_batches(
        sources=["1", "2"],
        positions=positions,
        grouping_config=None,
    )

    assert len(batches) == 2

    assert batches[0].group_id == "1"
    assert batches[0].source == "1"
    assert batches[0].source_index == 0
    np.testing.assert_array_equal(batches[0].positions, positions["1"])

    assert batches[1].group_id == "2"
    assert batches[1].source == "2"
    assert batches[1].source_index == 1
    np.testing.assert_array_equal(batches[1].positions, positions["2"])


def test_fixed_grouping_splits_positions_by_max_group_size():
    positions = {
        "1": np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [2.0, 2.0],
                [3.0, 3.0],
                [4.0, 4.0],
            ]
        )
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=2,
        distribution="fixed",
        min_group_size=1,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1"],
        positions=positions,
        grouping_config=grouping_config,
    )

    assert [batch.group_id for batch in batches] == ["1__g0", "1__g1", "1__g2"]
    assert [batch.source for batch in batches] == ["1", "1", "1"]
    assert [batch.source_index for batch in batches] == [0, 0, 0]
    assert [len(batch.positions) for batch in batches] == [2, 2, 1]


def test_fixed_grouping_keeps_all_agents_once():
    positions = {
        "1": np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [2.0, 2.0],
                [3.0, 3.0],
                [4.0, 4.0],
            ]
        )
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=2,
        distribution="fixed",
        min_group_size=1,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1"],
        positions=positions,
        grouping_config=grouping_config,
    )

    grouped_positions = np.vstack([batch.positions for batch in batches])

    assert sorted(map(tuple, grouped_positions)) == sorted(map(tuple, positions["1"]))


def test_fixed_grouping_handles_multiple_sources():
    positions = {
        "1": np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]),
        "2": np.array([[3.0, 3.0], [4.0, 4.0]]),
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=2,
        distribution="fixed",
        min_group_size=1,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1", "2"],
        positions=positions,
        grouping_config=grouping_config,
    )

    assert [batch.group_id for batch in batches] == [
        "1__g0",
        "1__g1",
        "2__g0",
    ]

    assert [len(batch.positions) for batch in batches] == [2, 1, 2]


def test_uniform_grouping_respects_size_bounds():
    positions = {
        "1": np.array([[float(i), float(i)] for i in range(20)])
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=5,
        distribution="uniform",
        min_group_size=2,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1"],
        positions=positions,
        grouping_config=grouping_config,
    )

    assert sum(len(batch.positions) for batch in batches) == 20

    for batch in batches[:-1]:
        assert 2 <= len(batch.positions) <= 5

    assert 1 <= len(batches[-1].positions) <= 5


def test_normal_grouping_respects_size_bounds():
    positions = {
        "1": np.array([[float(i), float(i)] for i in range(30)])
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=8,
        distribution="normal",
        min_group_size=2,
        mean_group_size=5.0,
        std_group_size=1.0,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1"],
        positions=positions,
        grouping_config=grouping_config,
    )

    assert sum(len(batch.positions) for batch in batches) == 30

    for batch in batches[:-1]:
        assert 2 <= len(batch.positions) <= 8

    assert 1 <= len(batches[-1].positions) <= 8


def test_grouping_returns_no_batches_for_empty_source_positions():
    positions = {
        "1": np.empty((0, 2)),
    }

    grouping_config = GroupDistributionConfig(
        max_group_size=5,
        distribution="fixed",
        min_group_size=1,
        seed=123,
    )

    batches = build_group_position_batches(
        sources=["1"],
        positions=positions,
        grouping_config=grouping_config,
    )

    assert batches == []