from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


SUPPORTED_NO_PATH_POLICIES = {"raise", "wait", "keep_current"}


@dataclass(frozen=True)
class CapacityReservationConfig:
    """
    Configuration for the current capacity reservation model used by h1/h2/h3.

    This replaces the old temporal_capacity configuration. The reservation model
    uses discrete time buckets to reserve edge-flow and node-occupancy resources.
    """

    bucket_size_frames: int = 30
    search_horizon_frames: int = 300
    traversal_time_scale: float = 1.0
    node_hold_frames: int | None = None

    node_capacity_default: int = 20
    edge_flow_capacity_default: int = 10

    # If enabled, groups larger than a resource capacity can reserve the
    # resource progressively: the reservation uses at most the resource capacity
    # per bucket and extends the traversal/hold time across multiple buckets.
    allow_oversized_group_reservations: bool = True

    # Optional guardrail for the previous behaviour. None means no explicit
    # limit; values <= 0 are treated as None.
    max_oversized_capacity_batches: int | None = None


@dataclass(frozen=True)
class CongestionConfig:
    node_capacity_multiplier: float = 1.0
    edge_flow_capacity_multiplier: float = 1.0

    block_edges_at_capacity: bool = False
    no_path_policy: str = "raise"

    capacity_reservations: CapacityReservationConfig = field(
        default_factory=CapacityReservationConfig
    )


def _build_capacity_reservation_config(
    congestion_cfg: Mapping[str, Any],
) -> CapacityReservationConfig:
    reservation_cfg = congestion_cfg.get("capacity_reservations", {})

    if reservation_cfg is None:
        reservation_cfg = {}

    if not isinstance(reservation_cfg, Mapping):
        raise TypeError(
            "congestion.capacity_reservations must be a mapping when provided"
        )

    bucket_size_frames = int(
        reservation_cfg.get("bucket_size_frames", 30)
    )

    search_horizon_frames = int(
        reservation_cfg.get("search_horizon_frames", 300)
    )

    if bucket_size_frames <= 0:
        raise ValueError(
            "congestion.capacity_reservations.bucket_size_frames must be > 0"
        )

    if search_horizon_frames < 0:
        raise ValueError(
            "congestion.capacity_reservations.search_horizon_frames must be >= 0"
        )

    node_hold_frames_raw = reservation_cfg.get("node_hold_frames", None)

    if node_hold_frames_raw is None:
        node_hold_frames = None
    else:
        node_hold_frames = int(node_hold_frames_raw)
        if node_hold_frames <= 0:
            raise ValueError(
                "congestion.capacity_reservations.node_hold_frames must be > 0"
            )

    node_capacity_default = int(
        reservation_cfg.get("node_capacity_default", 20)
    )

    edge_flow_capacity_default = int(
        reservation_cfg.get("edge_flow_capacity_default", 10)
    )

    if node_capacity_default <= 0:
        raise ValueError(
            "congestion.capacity_reservations.node_capacity_default must be > 0"
        )

    if edge_flow_capacity_default <= 0:
        raise ValueError(
            "congestion.capacity_reservations.edge_flow_capacity_default must be > 0"
        )

    allow_oversized_group_reservations = bool(
        reservation_cfg.get("allow_oversized_group_reservations", True)
    )

    max_oversized_capacity_batches_raw = reservation_cfg.get(
        "max_oversized_capacity_batches",
        None,
    )

    if max_oversized_capacity_batches_raw is None:
        max_oversized_capacity_batches = None
    else:
        max_oversized_capacity_batches = int(max_oversized_capacity_batches_raw)
        if max_oversized_capacity_batches <= 0:
            max_oversized_capacity_batches = None

    return CapacityReservationConfig(
        bucket_size_frames=bucket_size_frames,
        search_horizon_frames=search_horizon_frames,
        traversal_time_scale=float(
            reservation_cfg.get("traversal_time_scale", 1.0)
        ),
        node_hold_frames=node_hold_frames,
        node_capacity_default=node_capacity_default,
        edge_flow_capacity_default=edge_flow_capacity_default,
        allow_oversized_group_reservations=allow_oversized_group_reservations,
        max_oversized_capacity_batches=max_oversized_capacity_batches,
    )


def build_congestion_config(
    cfg: Mapping[str, Any],
) -> CongestionConfig:
    """
    Build optional congestion configuration from a case config.

    The current capacity model uses:
      - node_capacity_multiplier for node_capacity
      - edge_flow_capacity_multiplier for edge flow_capacity
      - capacity_reservations for time-bucket capacity reservations.

    The legacy edge_capacity_multiplier and temporal_capacity keys are
    intentionally not supported.
    """
    congestion_cfg = cfg.get("congestion")

    if congestion_cfg is None:
        return CongestionConfig()

    if not isinstance(congestion_cfg, Mapping):
        raise TypeError("congestion must be a mapping when provided")

    if "edge_capacity_multiplier" in congestion_cfg:
        raise ValueError(
            "congestion.edge_capacity_multiplier is deprecated and no longer "
            "supported. Use congestion.edge_flow_capacity_multiplier for edge "
            "flow_capacity and congestion.node_capacity_multiplier for "
            "node_capacity."
        )

    if "temporal_capacity" in congestion_cfg:
        raise ValueError(
            "congestion.temporal_capacity is deprecated and no longer supported. "
            "Use congestion.capacity_reservations instead."
        )

    node_capacity_multiplier = float(
        congestion_cfg.get("node_capacity_multiplier", 1.0)
    )

    edge_flow_capacity_multiplier = float(
        congestion_cfg.get("edge_flow_capacity_multiplier", 1.0)
    )

    if node_capacity_multiplier <= 0:
        raise ValueError("congestion.node_capacity_multiplier must be > 0")

    if edge_flow_capacity_multiplier <= 0:
        raise ValueError("congestion.edge_flow_capacity_multiplier must be > 0")

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
        node_capacity_multiplier=node_capacity_multiplier,
        edge_flow_capacity_multiplier=edge_flow_capacity_multiplier,
        block_edges_at_capacity=bool(
            congestion_cfg.get("block_edges_at_capacity", True)
        ),
        no_path_policy=no_path_policy,
        capacity_reservations=_build_capacity_reservation_config(congestion_cfg),
    )