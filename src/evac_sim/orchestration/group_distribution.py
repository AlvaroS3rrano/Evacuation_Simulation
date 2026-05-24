from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from evac_sim.orchestration.grouping_config import GroupDistributionConfig


@dataclass(frozen=True)
class GroupPositionBatch:
    group_id: str
    source: Any
    source_index: int
    positions: np.ndarray


def _clamp_group_size(
    value: int,
    *,
    min_group_size: int,
    max_group_size: int,
    remaining_agents: int,
) -> int:
    return max(
        1,
        min(
            remaining_agents,
            max(
                min_group_size,
                min(value, max_group_size),
            ),
        ),
    )


def _sample_group_size(
    *,
    remaining_agents: int,
    grouping_config: GroupDistributionConfig,
    rng: np.random.Generator,
) -> int:
    if remaining_agents <= grouping_config.max_group_size:
        return remaining_agents

    if grouping_config.distribution == "fixed":
        sampled_size = grouping_config.max_group_size

    elif grouping_config.distribution == "uniform":
        sampled_size = int(
            rng.integers(
                grouping_config.min_group_size,
                grouping_config.max_group_size + 1,
            )
        )

    elif grouping_config.distribution == "normal":
        mean = (
            grouping_config.mean_group_size
            if grouping_config.mean_group_size is not None
            else (grouping_config.min_group_size + grouping_config.max_group_size) / 2
        )

        std = (
            grouping_config.std_group_size
            if grouping_config.std_group_size is not None
            else max(1.0, grouping_config.max_group_size / 4)
        )

        sampled_size = int(round(rng.normal(mean, std)))

    else:
        raise ValueError(
            f"Unsupported grouping distribution: {grouping_config.distribution!r}"
        )

    return _clamp_group_size(
        sampled_size,
        min_group_size=grouping_config.min_group_size,
        max_group_size=grouping_config.max_group_size,
        remaining_agents=remaining_agents,
    )


def _split_source_positions(
    *,
    source: Any,
    source_index: int,
    source_positions: np.ndarray,
    grouping_config: GroupDistributionConfig,
    rng: np.random.Generator,
) -> list[GroupPositionBatch]:
    source_positions = np.asarray(source_positions)

    if len(source_positions) == 0:
        return []

    shuffled_indices = rng.permutation(len(source_positions))
    shuffled_positions = source_positions[shuffled_indices]

    batches: list[GroupPositionBatch] = []
    offset = 0
    group_index = 0

    while offset < len(shuffled_positions):
        remaining_agents = len(shuffled_positions) - offset

        group_size = _sample_group_size(
            remaining_agents=remaining_agents,
            grouping_config=grouping_config,
            rng=rng,
        )

        group_positions = shuffled_positions[offset : offset + group_size]

        batches.append(
            GroupPositionBatch(
                group_id=f"{source}__g{group_index}",
                source=source,
                source_index=source_index,
                positions=group_positions,
            )
        )

        offset += group_size
        group_index += 1

    return batches


def build_group_position_batches(
    *,
    sources: list[Any],
    positions: dict[Any, np.ndarray],
    grouping_config: GroupDistributionConfig | None,
) -> list[GroupPositionBatch]:
    """
    Build position batches used to create initial AgentGroup objects.

    If grouping_config is None, this preserves the previous behavior:
    one batch per source, containing all agents from that source.
    """

    if grouping_config is None:
        return [
            GroupPositionBatch(
                group_id=str(source),
                source=source,
                source_index=source_index,
                positions=positions[source],
            )
            for source_index, source in enumerate(sources)
        ]

    rng = np.random.default_rng(grouping_config.seed)

    batches: list[GroupPositionBatch] = []

    for source_index, source in enumerate(sources):
        batches.extend(
            _split_source_positions(
                source=source,
                source_index=source_index,
                source_positions=positions[source],
                grouping_config=grouping_config,
                rng=rng,
            )
        )

    return batches