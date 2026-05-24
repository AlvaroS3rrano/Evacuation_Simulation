from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SUPPORTED_GROUP_SIZE_DISTRIBUTIONS = {"fixed", "normal", "uniform"}


@dataclass(frozen=True)
class GroupDistributionConfig:
    """
    Optional configuration for splitting agents from one source into groups.

    This commit only adds the config model. The actual group splitting logic
    will be implemented later, so simulations keep their current behavior
    unless this config is explicitly consumed.
    """

    max_group_size: int
    distribution: str = "fixed"
    min_group_size: int = 1
    mean_group_size: float | None = None
    std_group_size: float | None = None
    seed: int | None = None


def build_group_distribution_config(
    cfg: Mapping[str, Any],
) -> GroupDistributionConfig | None:
    """
    Build optional group distribution config from a case config.

    If the `grouping` section is missing, or if it is explicitly disabled with
    `enabled: false`, this returns None. That keeps the current behavior:
    all agents that start in the same source are handled as one group.
    """

    grouping_cfg = cfg.get("grouping")

    if grouping_cfg is None:
        return None

    if not isinstance(grouping_cfg, Mapping):
        raise TypeError("grouping must be a mapping when provided")

    if grouping_cfg.get("enabled", True) is False:
        return None

    if "max_group_size" not in grouping_cfg:
        raise ValueError(
            "grouping.max_group_size is required when grouping is enabled"
        )

    max_group_size = int(grouping_cfg["max_group_size"])
    min_group_size = int(grouping_cfg.get("min_group_size", 1))
    distribution = str(grouping_cfg.get("distribution", "fixed")).lower()

    if distribution not in SUPPORTED_GROUP_SIZE_DISTRIBUTIONS:
        raise ValueError(
            "Unsupported grouping.distribution: "
            f"{distribution!r}. Expected one of "
            f"{sorted(SUPPORTED_GROUP_SIZE_DISTRIBUTIONS)}"
        )

    if max_group_size <= 0:
        raise ValueError("grouping.max_group_size must be > 0")

    if min_group_size <= 0:
        raise ValueError("grouping.min_group_size must be > 0")

    if min_group_size > max_group_size:
        raise ValueError(
            "grouping.min_group_size cannot be greater than "
            "grouping.max_group_size"
        )

    mean_group_size = grouping_cfg.get(
        "mean_group_size",
        grouping_cfg.get("mean"),
    )
    if mean_group_size is not None:
        mean_group_size = float(mean_group_size)
        if mean_group_size <= 0:
            raise ValueError("grouping.mean_group_size must be > 0")

    std_group_size = grouping_cfg.get(
        "std_group_size",
        grouping_cfg.get("std"),
    )
    if std_group_size is not None:
        std_group_size = float(std_group_size)
        if std_group_size < 0:
            raise ValueError("grouping.std_group_size must be >= 0")

    seed = grouping_cfg.get("seed")
    if seed is not None:
        seed = int(seed)

    return GroupDistributionConfig(
        max_group_size=max_group_size,
        distribution=distribution,
        min_group_size=min_group_size,
        mean_group_size=mean_group_size,
        std_group_size=std_group_size,
        seed=seed,
    )