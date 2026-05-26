from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SUPPORTED_NO_PATH_POLICIES = {"raise", "wait", "keep_current"}


@dataclass(frozen=True)
class CongestionConfig:
    edge_capacity_multiplier: float = 1.0

    # Backward-compatible defaults:
    # If no `congestion` section exists, old h1/h2 cost behavior is preserved.
    use_linear_congestion_cost: bool = False
    block_edges_at_capacity: bool = False
    no_path_policy: str = "raise"


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
      - missing initial paths still raise errors
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

    no_path_policy = str(
        congestion_cfg.get("no_path_policy", "wait")
    ).lower()

    if no_path_policy not in SUPPORTED_NO_PATH_POLICIES:
        raise ValueError(
            "Unsupported congestion.no_path_policy: "
            f"{no_path_policy!r}. Expected one of "
            f"{sorted(SUPPORTED_NO_PATH_POLICIES)}"
        )

    return CongestionConfig(
        edge_capacity_multiplier=edge_capacity_multiplier,
        use_linear_congestion_cost=bool(
            congestion_cfg.get("use_linear_congestion_cost", True)
        ),
        block_edges_at_capacity=bool(
            congestion_cfg.get("block_edges_at_capacity", True)
        ),
        no_path_policy=no_path_policy,
    )