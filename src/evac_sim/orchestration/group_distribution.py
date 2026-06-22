from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from evac_sim.orchestration.grouping_config import GroupDistributionConfig


@dataclass(frozen=True)
class GroupPositionBatch:
    group_id: str
    source: Any
    source_index: int
    positions: np.ndarray
    order_index: int = 0


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


def _sort_positions_by_route_proximity(
    source_positions: np.ndarray,
    target_xy: tuple[float, float] | None,
) -> np.ndarray:
    """
    Sort positions from closest to farthest relative to the next route node.

    This makes the first generated groups contain the agents that are physically
    closer to the next waypoint, reducing the chance that rear agents are
    assigned before front agents.
    """
    if target_xy is None:
        return source_positions

    if len(source_positions) == 0:
        return source_positions

    positions_xy = np.asarray(source_positions, dtype=float)

    if positions_xy.ndim != 2 or positions_xy.shape[1] < 2:
        raise ValueError(
            "source_positions must be a 2D array with at least x/y columns"
        )

    target = np.asarray(target_xy, dtype=float)

    distances = np.linalg.norm(
        positions_xy[:, :2] - target[:2],
        axis=1,
    )

    ordered_indices = np.argsort(distances, kind="stable")

    return source_positions[ordered_indices]


def _split_source_positions(
    *,
    source: Any,
    source_index: int,
    source_positions: np.ndarray,
    grouping_config: GroupDistributionConfig,
    rng: np.random.Generator,
    route_sort_target: tuple[float, float] | None = None,
) -> list[GroupPositionBatch]:
    source_positions = np.asarray(source_positions)

    if len(source_positions) == 0:
        return []

    if grouping_config.order_by_route_proximity:
        ordered_positions = _sort_positions_by_route_proximity(
            source_positions,
            route_sort_target,
        )
    else:
        shuffled_indices = rng.permutation(len(source_positions))
        ordered_positions = source_positions[shuffled_indices]

    batches: list[GroupPositionBatch] = []
    offset = 0
    group_index = 0

    while offset < len(ordered_positions):
        remaining_agents = len(ordered_positions) - offset

        group_size = _sample_group_size(
            remaining_agents=remaining_agents,
            grouping_config=grouping_config,
            rng=rng,
        )

        group_positions = ordered_positions[offset : offset + group_size]

        batches.append(
            GroupPositionBatch(
                group_id=f"{source}__g{group_index}",
                source=source,
                source_index=source_index,
                positions=group_positions,
                order_index=group_index,
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
    route_sort_targets_by_source: Mapping[Any, tuple[float, float]] | None = None,
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
                order_index=0,
            )
            for source_index, source in enumerate(sources)
        ]

    rng = np.random.default_rng(grouping_config.seed)

    batches: list[GroupPositionBatch] = []
    route_sort_targets_by_source = route_sort_targets_by_source or {}

    for source_index, source in enumerate(sources):
        batches.extend(
            _split_source_positions(
                source=source,
                source_index=source_index,
                source_positions=positions[source],
                grouping_config=grouping_config,
                rng=rng,
                route_sort_target=route_sort_targets_by_source.get(source),
            )
        )

    return batches