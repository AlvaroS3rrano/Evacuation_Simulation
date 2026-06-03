from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
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

    @cached_property
    def horizon_buckets(self) -> int:
        return max(
            0,
            int(math.ceil(self.temporal_horizon_frames / self.time_bucket_frames)),
        )

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
    reset_temporal_capacity_runtime_cache(G)
    return state

def reset_temporal_capacity_runtime_cache(G: Any) -> None:
    G.graph.pop("temporal_capacity_runtime_cache", None)


def _normalise_capacity(value: Any, default: int = 1) -> int:
    try:
        return max(1, int(math.ceil(float(value))))
    except (TypeError, ValueError):
        return max(1, int(default))


def _build_temporal_capacity_runtime_cache(
    G: Any,
    cfg: TemporalCapacityConfig,
) -> dict[str, dict]:
    """
    Build fast lookup dictionaries for temporal capacity evaluation.

    This avoids repeated NetworkX view lookups and repeated capacity conversions
    inside compute_temporal_path_effective_cost, which is called very frequently.
    """
    edge_cost: dict[tuple[Any, Any], float] = {}
    edge_traversal_frames: dict[tuple[Any, Any], int] = {}
    edge_flow_capacity: dict[tuple[Any, Any], int] = {}

    for u, v, edge_data in G.edges(data=True):
        edge_key = (u, v)

        cost = float(edge_data.get("cost", 1.0))
        edge_cost[edge_key] = cost
        edge_traversal_frames[edge_key] = max(
            1,
            int(math.ceil(cost * cfg.traversal_time_scale)),
        )

        flow_capacity = edge_data.get(
            "flow_capacity",
            edge_data.get("capacity", cfg.edge_flow_capacity_default),
        )

        edge_flow_capacity[edge_key] = (
            10**12
            if not cfg.edge_flow_enabled
            else _normalise_capacity(
                flow_capacity,
                default=cfg.edge_flow_capacity_default,
            )
        )

    node_capacity: dict[Any, int] = {}

    for node, node_data in G.nodes(data=True):
        capacity = node_data.get(
            "node_capacity",
            cfg.node_capacity_default,
        )

        node_capacity[node] = (
            10**12
            if not cfg.node_capacity_enabled
            else _normalise_capacity(
                capacity,
                default=cfg.node_capacity_default,
            )
        )

    cache = {
        "edge_cost": edge_cost,
        "edge_traversal_frames": edge_traversal_frames,
        "edge_flow_capacity": edge_flow_capacity,
        "node_capacity": node_capacity,
    }

    G.graph["temporal_capacity_runtime_cache"] = cache

    return cache


def _get_temporal_capacity_runtime_cache(
    G: Any,
    cfg: TemporalCapacityConfig,
) -> dict[str, dict]:
    cache = G.graph.get("temporal_capacity_runtime_cache")

    if cache is not None:
        return cache

    return _build_temporal_capacity_runtime_cache(G, cfg)

def _capacity_as_int(value: Any, default: int = 1) -> int:
    """
    Slow fallback used only when a graph was not normalised beforehand.
    """
    try:
        return max(1, int(math.ceil(float(value))))
    except (TypeError, ValueError):
        return max(1, int(default))


def _edge_flow_capacity(G: Any, u: Any, v: Any, cfg: TemporalCapacityConfig) -> int:
    if not cfg.edge_flow_enabled:
        return 10**12

    edge_data = G[u][v]

    flow_capacity = edge_data.get("flow_capacity")
    if isinstance(flow_capacity, int):
        return flow_capacity

    if flow_capacity is not None:
        flow_capacity = _capacity_as_int(
            flow_capacity,
            default=cfg.edge_flow_capacity_default,
        )
    else:
        flow_capacity = _capacity_as_int(
            edge_data.get("capacity", cfg.edge_flow_capacity_default),
            default=cfg.edge_flow_capacity_default,
        )

    edge_data["flow_capacity"] = flow_capacity
    return flow_capacity


def _node_capacity(G: Any, node: Any, cfg: TemporalCapacityConfig) -> int:
    if not cfg.node_capacity_enabled:
        return 10**12

    node_data = G.nodes[node]

    node_capacity = node_data.get("node_capacity")
    if isinstance(node_capacity, int):
        return node_capacity

    if node_capacity is not None:
        node_capacity = _capacity_as_int(
            node_capacity,
            default=cfg.node_capacity_default,
        )
    else:
        node_capacity = _capacity_as_int(
            node_data.get("capacity", cfg.node_capacity_default),
            default=cfg.node_capacity_default,
        )

    node_data["node_capacity"] = node_capacity
    return node_capacity

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

    Optimised version:
      - uses precomputed graph lookup dictionaries
      - avoids repeated NetworkX edge/node view access
      - inlines projected value and feasibility checks
      - avoids per-edge helper function calls in the hot loop
    """
    if not path or len(path) < 2:
        return float("inf")

    cfg = get_temporal_capacity_config(G)

    runtime_cache = _get_temporal_capacity_runtime_cache(G, cfg)
    edge_cost = runtime_cache["edge_cost"]
    edge_traversal_frames = runtime_cache["edge_traversal_frames"]

    if not cfg.enabled:
        return sum(
            edge_cost[(u, v)]
            for u, v in zip(path, path[1:])
        )

    if current_frame is None:
        current_frame = int(G.graph.get("current_frame", 0))

    state = get_temporal_capacity_state(G)

    if state is None:
        edge_flow_reservations = {}
        node_occupancy_reservations = {}
    else:
        edge_flow_reservations = state.edge_flow
        node_occupancy_reservations = state.node_occupancy

    edge_flow_capacity = runtime_cache["edge_flow_capacity"]
    node_capacity = runtime_cache["node_capacity"]

    time_bucket_frames = cfg.time_bucket_frames
    current_bucket = int(current_frame // time_bucket_frames)
    last_bucket = current_bucket + cfg.horizon_buckets

    arrival_frame = int(current_frame)
    total = 0.0

    effective_group_size = max(0, int(group_size))

    beta_edge = beta if cfg.beta_edge is None else cfg.beta_edge
    beta_node = beta if cfg.beta_node is None else cfg.beta_node

    edge_exponent = cfg.edge_capacity_exponent
    node_exponent = cfg.node_capacity_exponent

    block_at_capacity = cfg.block_at_capacity
    allow_waiting = cfg.allow_waiting
    wait_penalty = cfg.wait_penalty

    for u, v in zip(path, path[1:]):
        edge_key = (u, v)

        base_cost = edge_cost[edge_key]
        traversal_frames = edge_traversal_frames[edge_key]

        bucket = int(arrival_frame // time_bucket_frames)
        wait_frames = 0

        if current_bucket <= bucket <= last_bucket:
            e_capacity = edge_flow_capacity[edge_key]
            n_capacity = node_capacity[v]

            projected_edge_flow = (
                edge_flow_reservations.get((u, v, bucket), 0)
                + effective_group_size
            )
            projected_node_occupancy = (
                node_occupancy_reservations.get((v, bucket), 0)
                + effective_group_size
            )

            feasible = (
                projected_edge_flow <= e_capacity
                and projected_node_occupancy <= n_capacity
            )

            if block_at_capacity and not feasible:
                if not allow_waiting:
                    return float("inf")

                feasible_bucket = None

                for candidate_bucket in range(bucket, last_bucket + 1):
                    candidate_edge_flow = (
                        edge_flow_reservations.get((u, v, candidate_bucket), 0)
                        + effective_group_size
                    )
                    candidate_node_occupancy = (
                        node_occupancy_reservations.get((v, candidate_bucket), 0)
                        + effective_group_size
                    )

                    if (
                        candidate_edge_flow <= e_capacity
                        and candidate_node_occupancy <= n_capacity
                    ):
                        feasible_bucket = candidate_bucket
                        projected_edge_flow = candidate_edge_flow
                        projected_node_occupancy = candidate_node_occupancy
                        break

                if feasible_bucket is None:
                    return float("inf")

                wait_frames = max(0, feasible_bucket - bucket) * time_bucket_frames
                arrival_frame += wait_frames
                bucket = feasible_bucket

            edge_ratio = projected_edge_flow / e_capacity
            node_ratio = projected_node_occupancy / n_capacity

            if edge_exponent == 1.0:
                edge_penalty = edge_ratio
            else:
                edge_penalty = edge_ratio ** edge_exponent

            if node_exponent == 1.0:
                node_penalty = node_ratio
            else:
                node_penalty = node_ratio ** node_exponent

            total += base_cost * (
                1.0
                + beta_edge * edge_penalty
                + beta_node * node_penalty
            )

            if wait_penalty:
                total += wait_penalty * wait_frames

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

    Optimised version using runtime capacity lookup dictionaries.
    """
    if not path or len(path) < 2:
        return False

    cfg = get_temporal_capacity_config(G)

    if not cfg.enabled or not cfg.temporal_reservation_enabled:
        return False

    state = ensure_temporal_capacity_state(G)

    state.release_group(group_id)

    runtime_cache = _get_temporal_capacity_runtime_cache(G, cfg)
    edge_traversal_frames = runtime_cache["edge_traversal_frames"]
    edge_flow_capacity = runtime_cache["edge_flow_capacity"]
    node_capacity = runtime_cache["node_capacity"]

    time_bucket_frames = cfg.time_bucket_frames
    current_bucket = int(current_frame // time_bucket_frames)
    last_bucket = current_bucket + cfg.horizon_buckets

    state.cleanup_before_bucket(current_bucket)

    edge_flow_reservations = state.edge_flow
    node_occupancy_reservations = state.node_occupancy

    edge_keys: set[tuple[Any, Any, int]] = set()
    node_keys: set[tuple[Any, int]] = set()

    arrival_frame = int(current_frame)
    effective_group_size = max(0, int(group_size))

    for u, v in zip(path, path[1:]):
        edge_key_static = (u, v)
        bucket = int(arrival_frame // time_bucket_frames)

        if current_bucket <= bucket <= last_bucket:
            e_capacity = edge_flow_capacity[edge_key_static]
            n_capacity = node_capacity[v]

            if cfg.block_at_capacity:
                projected_edge_flow = (
                    edge_flow_reservations.get((u, v, bucket), 0)
                    + effective_group_size
                )
                projected_node_occupancy = (
                    node_occupancy_reservations.get((v, bucket), 0)
                    + effective_group_size
                )

                feasible = (
                    projected_edge_flow <= e_capacity
                    and projected_node_occupancy <= n_capacity
                )

                if not feasible and cfg.allow_waiting:
                    feasible_bucket = None

                    for candidate_bucket in range(bucket, last_bucket + 1):
                        candidate_edge_flow = (
                            edge_flow_reservations.get((u, v, candidate_bucket), 0)
                            + effective_group_size
                        )
                        candidate_node_occupancy = (
                            node_occupancy_reservations.get((v, candidate_bucket), 0)
                            + effective_group_size
                        )

                        if (
                            candidate_edge_flow <= e_capacity
                            and candidate_node_occupancy <= n_capacity
                        ):
                            feasible_bucket = candidate_bucket
                            break

                    if feasible_bucket is None:
                        return False

                    arrival_frame += max(0, feasible_bucket - bucket) * time_bucket_frames
                    bucket = feasible_bucket

                elif not feasible:
                    return False

            edge_key = (u, v, bucket)
            node_key = (v, bucket)

            edge_keys.add(edge_key)
            node_keys.add(node_key)

            edge_flow_reservations[edge_key] = (
                edge_flow_reservations.get(edge_key, 0) + effective_group_size
            )
            node_occupancy_reservations[node_key] = (
                node_occupancy_reservations.get(node_key, 0) + effective_group_size
            )

        arrival_frame += edge_traversal_frames[edge_key_static]

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