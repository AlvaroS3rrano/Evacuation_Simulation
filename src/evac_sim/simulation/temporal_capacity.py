from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemporalCapacityConfig:
    """
    Rolling-horizon temporal capacity configuration.

    The model separates:
      - node occupancy capacity: how many agents can be expected in an area/node
      - edge flow capacity: how many agents can be expected to traverse an edge per time bucket
    """

    enabled: bool = False
    node_capacity_enabled: bool = True
    edge_flow_enabled: bool = True
    temporal_reservation_enabled: bool = True

    time_bucket_frames: int = 30
    temporal_horizon_frames: int = 300

    traversal_time_scale: float = 1.0

    node_capacity_default: int = 20
    edge_flow_capacity_default: int = 10

    beta_edge: float | None = None
    beta_node: float | None = None

    edge_capacity_exponent: float = 1.0
    node_capacity_exponent: float = 1.0

    wait_penalty: float = 0.0
    allow_waiting: bool = True
    block_at_capacity: bool = True

    @property
    def horizon_buckets(self) -> int:
        return max(0, int(math.ceil(self.temporal_horizon_frames / self.time_bucket_frames)))

    def bucket_for_frame(self, frame: int | float) -> int:
        return int(math.floor(float(frame) / self.time_bucket_frames))


@dataclass
class TemporalCapacityState:
    """
    Temporal reservation state.

    Reservations are keyed by discrete time bucket. This avoids blocking a route
    because of a bottleneck that is occupied now but may be free when the group arrives.
    """

    edge_flow: dict[tuple[Any, Any, int], int] = field(default_factory=dict)
    node_occupancy: dict[tuple[Any, int], int] = field(default_factory=dict)
    group_reservations: dict[
        Any,
        tuple[
            set[tuple[Any, Any, int]],
            set[tuple[Any, int]],
            int,
        ],
    ] = field(default_factory=dict)

    def get_edge_flow(self, u: Any, v: Any, bucket: int) -> int:
        return int(self.edge_flow.get((u, v, bucket), 0))

    def get_node_occupancy(self, node: Any, bucket: int) -> int:
        return int(self.node_occupancy.get((node, bucket), 0))

    def release_group(self, group_id: Any) -> None:
        reservation = self.group_reservations.pop(group_id, None)
        if reservation is None:
            return

        edge_keys, node_keys, group_size = reservation

        for key in edge_keys:
            self.edge_flow[key] = max(0, self.edge_flow.get(key, 0) - group_size)
            if self.edge_flow[key] == 0:
                self.edge_flow.pop(key, None)

        for key in node_keys:
            self.node_occupancy[key] = max(0, self.node_occupancy.get(key, 0) - group_size)
            if self.node_occupancy[key] == 0:
                self.node_occupancy.pop(key, None)

    def cleanup_before_bucket(self, bucket: int) -> None:
        self.edge_flow = {
            key: value
            for key, value in self.edge_flow.items()
            if key[2] >= bucket
        }
        self.node_occupancy = {
            key: value
            for key, value in self.node_occupancy.items()
            if key[1] >= bucket
        }


def get_temporal_capacity_config(G: Any) -> TemporalCapacityConfig:
    cfg = G.graph.get("temporal_capacity_config")
    if isinstance(cfg, TemporalCapacityConfig):
        return cfg
    return TemporalCapacityConfig()


def ensure_temporal_capacity_state(G: Any) -> TemporalCapacityState:
    state = G.graph.get("temporal_capacity_state")
    if isinstance(state, TemporalCapacityState):
        return state

    state = TemporalCapacityState()
    G.graph["temporal_capacity_state"] = state
    return state


def get_temporal_capacity_state(G: Any) -> TemporalCapacityState | None:
    state = G.graph.get("temporal_capacity_state")
    if isinstance(state, TemporalCapacityState):
        return state
    return None


def reset_temporal_capacity_state(G: Any) -> TemporalCapacityState:
    state = TemporalCapacityState()
    G.graph["temporal_capacity_state"] = state
    return state


def _capacity_as_int(value: Any, default: int = 1) -> int:
    try:
        return max(1, int(math.ceil(float(value))))
    except (TypeError, ValueError):
        return max(1, int(default))


def _edge_flow_capacity(G: Any, u: Any, v: Any, cfg: TemporalCapacityConfig) -> int:
    if not cfg.edge_flow_enabled:
        return 10**12

    edge_data = G[u][v]
    return _capacity_as_int(
        edge_data.get(
            "flow_capacity",
            edge_data.get("capacity", cfg.edge_flow_capacity_default),
        ),
        default=cfg.edge_flow_capacity_default,
    )


def _node_capacity(G: Any, node: Any, cfg: TemporalCapacityConfig) -> int:
    if not cfg.node_capacity_enabled:
        return 10**12

    node_data = G.nodes[node]
    return _capacity_as_int(
        node_data.get(
            "node_capacity",
            node_data.get("capacity", cfg.node_capacity_default),
        ),
        default=cfg.node_capacity_default,
    )


def _edge_traversal_frames(edge_data: dict, cfg: TemporalCapacityConfig) -> int:
    base_cost = float(edge_data.get("cost", 1.0))
    return max(1, int(math.ceil(base_cost * cfg.traversal_time_scale)))


def _within_horizon(bucket: int, current_bucket: int, cfg: TemporalCapacityConfig) -> bool:
    return current_bucket <= bucket <= current_bucket + cfg.horizon_buckets


def _projected_values(
    *,
    G: Any,
    state: TemporalCapacityState | None,
    u: Any,
    v: Any,
    bucket: int,
    group_size: int,
    cfg: TemporalCapacityConfig,
) -> tuple[int, int, int, int]:
    edge_capacity = _edge_flow_capacity(G, u, v, cfg)
    node_capacity = _node_capacity(G, v, cfg)

    edge_flow = state.get_edge_flow(u, v, bucket) if state is not None else 0
    node_occupancy = state.get_node_occupancy(v, bucket) if state is not None else 0

    return (
        edge_flow + group_size,
        edge_capacity,
        node_occupancy + group_size,
        node_capacity,
    )


def _is_feasible(
    *,
    projected_edge_flow: int,
    edge_capacity: int,
    projected_node_occupancy: int,
    node_capacity: int,
) -> bool:
    return (
        projected_edge_flow <= edge_capacity
        and projected_node_occupancy <= node_capacity
    )


def _first_feasible_bucket(
    *,
    G: Any,
    state: TemporalCapacityState | None,
    u: Any,
    v: Any,
    start_bucket: int,
    current_bucket: int,
    group_size: int,
    cfg: TemporalCapacityConfig,
) -> int | None:
    last_bucket = current_bucket + cfg.horizon_buckets

    for bucket in range(start_bucket, last_bucket + 1):
        projected_edge_flow, edge_capacity, projected_node_occupancy, node_capacity = (
            _projected_values(
                G=G,
                state=state,
                u=u,
                v=v,
                bucket=bucket,
                group_size=group_size,
                cfg=cfg,
            )
        )

        if _is_feasible(
            projected_edge_flow=projected_edge_flow,
            edge_capacity=edge_capacity,
            projected_node_occupancy=projected_node_occupancy,
            node_capacity=node_capacity,
        ):
            return bucket

    return None


def compute_temporal_path_effective_cost(
    G: Any,
    path: list[Any],
    *,
    group_size: int = 0,
    beta: float = 1.0,
    current_frame: int | None = None,
) -> float:
    """
    Compute a temporal node/edge-capacity-aware path cost.

    h3 evaluates each edge and destination node at the estimated future bucket
    when the group is expected to reach it.
    """
    if not path or len(path) < 2:
        return float("inf")

    cfg = get_temporal_capacity_config(G)

    if not cfg.enabled:
        return sum(float(G[u][v]["cost"]) for u, v in zip(path, path[1:]))

    if current_frame is None:
        current_frame = int(G.graph.get("current_frame", 0))

    state = get_temporal_capacity_state(G)
    current_bucket = cfg.bucket_for_frame(current_frame)

    arrival_frame = float(current_frame)
    total = 0.0
    effective_group_size = max(0, int(group_size))

    beta_edge = beta if cfg.beta_edge is None else cfg.beta_edge
    beta_node = beta if cfg.beta_node is None else cfg.beta_node

    for u, v in zip(path, path[1:]):
        edge_data = G[u][v]
        base_cost = float(edge_data["cost"])
        traversal_frames = _edge_traversal_frames(edge_data, cfg)

        bucket = cfg.bucket_for_frame(arrival_frame)
        wait_frames = 0

        if _within_horizon(bucket, current_bucket, cfg):
            projected_edge_flow, edge_capacity, projected_node_occupancy, node_capacity = (
                _projected_values(
                    G=G,
                    state=state,
                    u=u,
                    v=v,
                    bucket=bucket,
                    group_size=effective_group_size,
                    cfg=cfg,
                )
            )

            feasible = _is_feasible(
                projected_edge_flow=projected_edge_flow,
                edge_capacity=edge_capacity,
                projected_node_occupancy=projected_node_occupancy,
                node_capacity=node_capacity,
            )

            if cfg.block_at_capacity and not feasible:
                if not cfg.allow_waiting:
                    return float("inf")

                feasible_bucket = _first_feasible_bucket(
                    G=G,
                    state=state,
                    u=u,
                    v=v,
                    start_bucket=bucket,
                    current_bucket=current_bucket,
                    group_size=effective_group_size,
                    cfg=cfg,
                )

                if feasible_bucket is None:
                    return float("inf")

                wait_frames = max(0, feasible_bucket - bucket) * cfg.time_bucket_frames
                arrival_frame += wait_frames
                bucket = feasible_bucket

                projected_edge_flow, edge_capacity, projected_node_occupancy, node_capacity = (
                    _projected_values(
                        G=G,
                        state=state,
                        u=u,
                        v=v,
                        bucket=bucket,
                        group_size=effective_group_size,
                        cfg=cfg,
                    )
                )

            edge_ratio = projected_edge_flow / edge_capacity
            node_ratio = projected_node_occupancy / node_capacity

            total += base_cost * (
                1.0
                + beta_edge * (edge_ratio ** cfg.edge_capacity_exponent)
                + beta_node * (node_ratio ** cfg.node_capacity_exponent)
            )
            total += cfg.wait_penalty * wait_frames
        else:
            total += base_cost

        arrival_frame += traversal_frames

    return total


def reserve_temporal_path(
    G: Any,
    path: list[Any],
    *,
    group_id: Any,
    group_size: int,
    current_frame: int,
) -> bool:
    """
    Reserve temporal edge-flow and destination-node buckets for a group path.
    """
    if not path or len(path) < 2:
        return False

    cfg = get_temporal_capacity_config(G)

    if not cfg.enabled or not cfg.temporal_reservation_enabled:
        return False

    state = ensure_temporal_capacity_state(G)

    state.release_group(group_id)

    current_bucket = cfg.bucket_for_frame(current_frame)
    state.cleanup_before_bucket(current_bucket)

    edge_keys: set[tuple[Any, Any, int]] = set()
    node_keys: set[tuple[Any, int]] = set()

    arrival_frame = float(current_frame)
    effective_group_size = max(0, int(group_size))

    for u, v in zip(path, path[1:]):
        edge_data = G[u][v]
        bucket = cfg.bucket_for_frame(arrival_frame)

        if _within_horizon(bucket, current_bucket, cfg):
            if cfg.block_at_capacity:
                projected_edge_flow, edge_capacity, projected_node_occupancy, node_capacity = (
                    _projected_values(
                        G=G,
                        state=state,
                        u=u,
                        v=v,
                        bucket=bucket,
                        group_size=effective_group_size,
                        cfg=cfg,
                    )
                )

                feasible = _is_feasible(
                    projected_edge_flow=projected_edge_flow,
                    edge_capacity=edge_capacity,
                    projected_node_occupancy=projected_node_occupancy,
                    node_capacity=node_capacity,
                )

                if not feasible and cfg.allow_waiting:
                    feasible_bucket = _first_feasible_bucket(
                        G=G,
                        state=state,
                        u=u,
                        v=v,
                        start_bucket=bucket,
                        current_bucket=current_bucket,
                        group_size=effective_group_size,
                        cfg=cfg,
                    )

                    if feasible_bucket is None:
                        return False

                    arrival_frame += max(0, feasible_bucket - bucket) * cfg.time_bucket_frames
                    bucket = feasible_bucket

                elif not feasible:
                    return False

            edge_key = (u, v, bucket)
            node_key = (v, bucket)

            edge_keys.add(edge_key)
            node_keys.add(node_key)

            state.edge_flow[edge_key] = state.edge_flow.get(edge_key, 0) + effective_group_size
            state.node_occupancy[node_key] = (
                state.node_occupancy.get(node_key, 0) + effective_group_size
            )

        arrival_frame += _edge_traversal_frames(edge_data, cfg)

    state.group_reservations[group_id] = (
        edge_keys,
        node_keys,
        effective_group_size,
    )

    return True


def release_temporal_path_reservation(G: Any, *, group_id: Any) -> None:
    state = get_temporal_capacity_state(G)
    if state is not None:
        state.release_group(group_id)