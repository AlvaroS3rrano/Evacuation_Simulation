from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CongestionConfig:
    edge_capacity_multiplier: float = 1.0

    # Backward-compatible defaults:
    # If no `congestion` section exists, old h1/h2 cost behavior is preserved.
    use_linear_congestion_cost: bool = False
    block_edges_at_capacity: bool = False


def build_congestion_config(
    cfg: Mapping[str, Any],
) -> CongestionConfig:
    """
    Build optional congestion configuration from a case config.

    If the `congestion` section is missing, default values preserve the previous
    behavior:
      - capacities are not scaled
      - h1/h2 use the legacy additive congestion cost
      - saturated edges are not blocked
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

        # If the user explicitly adds `congestion`, use the new behavior unless
        # they disable it.
        use_linear_congestion_cost=bool(
            congestion_cfg.get("use_linear_congestion_cost", True)
        ),
        block_edges_at_capacity=bool(
            congestion_cfg.get("block_edges_at_capacity", True)
        ),
    )