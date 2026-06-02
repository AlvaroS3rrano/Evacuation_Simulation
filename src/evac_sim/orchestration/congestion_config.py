from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from evac_sim.simulation.temporal_capacity import TemporalCapacityConfig


SUPPORTED_NO_PATH_POLICIES = {"raise", "wait", "keep_current"}


@dataclass(frozen=True)
class CongestionConfig:
    edge_capacity_multiplier: float = 1.0

    # Backward-compatible defaults:
    # If no `congestion` section exists, old h1/h2 cost behavior is preserved.
    use_linear_congestion_cost: bool = False
    block_edges_at_capacity: bool = False
    no_path_policy: str = "raise"

    temporal_capacity: TemporalCapacityConfig = field(
        default_factory=TemporalCapacityConfig
    )


def _build_temporal_capacity_config(
    congestion_cfg: Mapping[str, Any],
) -> TemporalCapacityConfig:
    temporal_cfg = congestion_cfg.get("temporal_capacity", {})

    if temporal_cfg is None:
        temporal_cfg = {}

    if not isinstance(temporal_cfg, Mapping):
        raise TypeError("congestion.temporal_capacity must be a mapping when provided")

    time_bucket_frames = int(temporal_cfg.get("time_bucket_frames", 30))
    temporal_horizon_frames = int(temporal_cfg.get("temporal_horizon_frames", 300))

    if time_bucket_frames <= 0:
        raise ValueError("congestion.temporal_capacity.time_bucket_frames must be > 0")

    if temporal_horizon_frames < 0:
        raise ValueError(
            "congestion.temporal_capacity.temporal_horizon_frames must be >= 0"
        )

    return TemporalCapacityConfig(
        enabled=bool(temporal_cfg.get("enabled", False)),
        node_capacity_enabled=bool(
            temporal_cfg.get("node_capacity_enabled", True)
        ),
        edge_flow_enabled=bool(
            temporal_cfg.get("edge_flow_enabled", True)
        ),
        temporal_reservation_enabled=bool(
            temporal_cfg.get("temporal_reservation_enabled", True)
        ),
        time_bucket_frames=time_bucket_frames,
        temporal_horizon_frames=temporal_horizon_frames,
        traversal_time_scale=float(
            temporal_cfg.get("traversal_time_scale", 1.0)
        ),
        node_capacity_default=int(
            temporal_cfg.get("node_capacity_default", 20)
        ),
        edge_flow_capacity_default=int(
            temporal_cfg.get("edge_flow_capacity_default", 10)
        ),
        beta_edge=(
            None
            if temporal_cfg.get("beta_edge", None) is None
            else float(temporal_cfg["beta_edge"])
        ),
        beta_node=(
            None
            if temporal_cfg.get("beta_node", None) is None
            else float(temporal_cfg["beta_node"])
        ),
        edge_capacity_exponent=float(
            temporal_cfg.get("edge_capacity_exponent", 1.0)
        ),
        node_capacity_exponent=float(
            temporal_cfg.get("node_capacity_exponent", 1.0)
        ),
        wait_penalty=float(
            temporal_cfg.get("wait_penalty", 0.0)
        ),
        allow_waiting=bool(
            temporal_cfg.get("allow_waiting", True)
        ),
        block_at_capacity=bool(
            temporal_cfg.get("block_at_capacity", True)
        ),
    )


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
      - h3 temporal capacity is disabled
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
        temporal_capacity=_build_temporal_capacity_config(congestion_cfg),
    )