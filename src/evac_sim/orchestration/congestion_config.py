from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CongestionConfig:
    edge_capacity_multiplier: float = 1.0


def build_congestion_config(
    cfg: Mapping[str, Any],
) -> CongestionConfig:
    """
    Build optional congestion configuration from a case config.

    If the `congestion` section is missing, default values are returned.
    This keeps the current behavior unchanged.
    """

    congestion_cfg = cfg.get("congestion")

    if congestion_cfg is None:
        return CongestionConfig()

    if not isinstance(congestion_cfg, Mapping):
        raise TypeError("congestion must be a mapping when provided")

    edge_capacity_multiplier = float(
        congestion_cfg.get("edge_capacity_multiplier", 1.0)
    )

    if edge_capacity_multiplier <= 0:
        raise ValueError("congestion.edge_capacity_multiplier must be > 0")

    return CongestionConfig(
        edge_capacity_multiplier=edge_capacity_multiplier,
    )