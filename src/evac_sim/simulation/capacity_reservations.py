from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


Resource = tuple[Any, ...]


@dataclass(frozen=True)
class ReservationInterval:
    resource: Resource
    start_frame: int
    end_frame: int
    start_bucket: int
    end_bucket: int
    amount: int
    path_edge_index: int | None = None


@dataclass
class PathSchedule:
    path: list[Any]
    start_frame: int
    arrival_frame: int
    intervals: list[ReservationInterval]
    first_departure_frame: int
    blocked_resource: Resource | None = None

    @property
    def wait_frames(self) -> int:
        return max(0, self.first_departure_frame - self.start_frame)


@dataclass
class ScheduleAttempt:
    schedule: PathSchedule | None
    blocked_resource: Resource | None = None
    earliest_retry_frame: int | None = None
    reason: str = "unknown"

    @property
    def feasible(self) -> bool:
        return self.schedule is not None

    @property
    def can_depart_now(self) -> bool:
        if self.schedule is None:
            return False

        return self.schedule.first_departure_frame <= self.schedule.start_frame


@dataclass(order=True)
class QueueEntry:
    priority: float
    enqueued_frame: int
    group_id: Any = field(compare=False)


class CapacityReservationManager:
    def __init__(
        self,
        G: Any,
        *,
        bucket_size_frames: int = 30,
        max_search_buckets: int = 30,
        traversal_time_scale: float = 1.0,
        node_hold_frames: int | None = None,
        node_capacity_default: int = 20,
        edge_flow_capacity_default: int = 10,
    ) -> None:
        self.G = G
        self.bucket_size_frames = max(1, int(bucket_size_frames))
        self.max_search_buckets = max(1, int(max_search_buckets))
        self.traversal_time_scale = float(traversal_time_scale)
        self.node_hold_frames = (
            self.bucket_size_frames
            if node_hold_frames is None
            else max(1, int(node_hold_frames))
        )
        self.node_capacity_default = int(node_capacity_default)
        self.edge_flow_capacity_default = int(edge_flow_capacity_default)

        self.reservations: dict[Resource, dict[int, dict[Any, int]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.group_reservations: dict[Any, PathSchedule] = {}
        self.waiting_queues: dict[Resource, list[QueueEntry]] = defaultdict(list)

    def bucket_for_frame(self, frame: int | float) -> int:
        return int(math.floor(float(frame) / self.bucket_size_frames))

    def _bucket_start_frame(self, bucket: int) -> int:
        return bucket * self.bucket_size_frames

    def _buckets_for_interval(self, start_frame: int, end_frame: int) -> range:
        start_bucket = self.bucket_for_frame(start_frame)
        end_bucket = self.bucket_for_frame(max(start_frame, end_frame - 1))
        return range(start_bucket, end_bucket + 1)

    def _normalise_capacity(self, value: Any, default: int) -> int:
        try:
            return max(1, int(math.ceil(float(value))))
        except (TypeError, ValueError):
            return max(1, int(default))

    def _resource_capacity(self, resource: Resource) -> int:
        if resource[0] == "node":
            node = resource[1]
            return self._normalise_capacity(
                self.G.nodes[node].get("node_capacity", self.node_capacity_default),
                self.node_capacity_default,
            )

        if resource[0] == "edge":
            _, u, v = resource
            return self._normalise_capacity(
                self.G[u][v].get("flow_capacity", self.edge_flow_capacity_default),
                self.edge_flow_capacity_default,
            )

        raise ValueError(f"Unknown capacity resource: {resource}")

    def _edge_traversal_frames(self, u: Any, v: Any) -> int:
        edge_data = self.G[u][v]
        base_cost = float(edge_data.get("cost", 1.0))
        return max(1, int(math.ceil(base_cost * self.traversal_time_scale)))

    def _reserved_amount(
        self,
        resource: Resource,
        bucket: int,
        *,
        ignore_group_id: Any | None = None,
    ) -> int:
        bucket_reservations = self.reservations.get(resource, {}).get(bucket, {})
        return sum(
            amount
            for group_id, amount in bucket_reservations.items()
            if group_id != ignore_group_id
        )

    def _has_capacity(
        self,
        resource: Resource,
        bucket: int,
        group_size: int,
        *,
        ignore_group_id: Any | None = None,
    ) -> bool:
        return (
            self._reserved_amount(
                resource,
                bucket,
                ignore_group_id=ignore_group_id,
            )
            + group_size
            <= self._resource_capacity(resource)
        )

    def _interval_has_capacity(
        self,
        resource: Resource,
        start_frame: int,
        end_frame: int,
        group_size: int,
        *,
        ignore_group_id: Any | None = None,
    ) -> bool:
        for bucket in self._buckets_for_interval(start_frame, end_frame):
            if not self._has_capacity(
                resource,
                bucket,
                group_size,
                ignore_group_id=ignore_group_id,
            ):
                return False
        return True

    def _build_interval(
        self,
        resource: Resource,
        start_frame: int,
        end_frame: int,
        group_size: int,
        *,
        path_edge_index: int | None = None,
    ) -> ReservationInterval:
        buckets = list(self._buckets_for_interval(start_frame, end_frame))
        return ReservationInterval(
            resource=resource,
            start_frame=start_frame,
            end_frame=end_frame,
            start_bucket=buckets[0],
            end_bucket=buckets[-1],
            amount=group_size,
            path_edge_index=path_edge_index,
        )

    def _first_feasible_start_for_step(
        self,
        *,
        edge_resource: Resource,
        node_resource: Resource,
        earliest_start_frame: int,
        traversal_frames: int,
        group_size: int,
        ignore_group_id: Any | None,
    ) -> tuple[int | None, Resource | None]:
        candidate_bucket = self.bucket_for_frame(earliest_start_frame)
        last_bucket = candidate_bucket + self.max_search_buckets

        first_blocked_resource: Resource | None = None

        for bucket in range(candidate_bucket, last_bucket + 1):
            step_start = max(earliest_start_frame, self._bucket_start_frame(bucket))
            edge_end = step_start + traversal_frames
            node_end = edge_end + self.node_hold_frames

            edge_ok = self._interval_has_capacity(
                edge_resource,
                step_start,
                edge_end,
                group_size,
                ignore_group_id=ignore_group_id,
            )
            node_ok = self._interval_has_capacity(
                node_resource,
                edge_end,
                node_end,
                group_size,
                ignore_group_id=ignore_group_id,
            )

            if edge_ok and node_ok:
                return step_start, None

            if first_blocked_resource is None:
                first_blocked_resource = edge_resource if not edge_ok else node_resource

        return None, first_blocked_resource

    def _limited_path_for_horizon(
        self,
        path: list[Any],
        horizon_edges: int | None,
    ) -> list[Any]:
        if horizon_edges is None:
            return list(path)

        return list(path[: max(1, horizon_edges + 1)])

    def attempt_earliest_feasible_schedule(
            self,
            path: list[Any],
            group_size: int,
            start_frame: int,
            *,
            horizon_edges: int | None = None,
            ignore_group_id: Any | None = None,
    ) -> ScheduleAttempt:
        path = self._limited_path_for_horizon(
            path,
            horizon_edges,
        )

        if not path or len(path) < 2:
            return ScheduleAttempt(
                schedule=None,
                reason="invalid_path",
            )

        group_size = max(1, int(group_size))
        cursor = int(start_frame)
        intervals: list[ReservationInterval] = []
        first_departure_frame: int | None = None
        first_blocked_resource: Resource | None = None

        for edge_index, (u, v) in enumerate(zip(path, path[1:])):
            edge_resource = ("edge", u, v)
            node_resource = ("node", v)
            traversal_frames = self._edge_traversal_frames(u, v)

            step_start, blocked_resource = self._first_feasible_start_for_step(
                edge_resource=edge_resource,
                node_resource=node_resource,
                earliest_start_frame=cursor,
                traversal_frames=traversal_frames,
                group_size=group_size,
                ignore_group_id=ignore_group_id,
            )

            if blocked_resource is not None and first_blocked_resource is None:
                first_blocked_resource = blocked_resource

            if step_start is None:
                earliest_retry_frame = None

                if first_blocked_resource is not None:
                    wait_time = self.estimate_wait_time(
                        first_blocked_resource,
                        group_size,
                        start_frame,
                    )

                    if wait_time is not None:
                        earliest_retry_frame = int(start_frame) + wait_time

                return ScheduleAttempt(
                    schedule=None,
                    blocked_resource=first_blocked_resource,
                    earliest_retry_frame=earliest_retry_frame,
                    reason="blocked",
                )

            if first_departure_frame is None:
                first_departure_frame = step_start

            edge_end = step_start + traversal_frames
            node_end = edge_end + self.node_hold_frames

            intervals.append(
                self._build_interval(
                    edge_resource,
                    step_start,
                    edge_end,
                    group_size,
                    path_edge_index=edge_index,
                )
            )

            intervals.append(
                self._build_interval(
                    node_resource,
                    edge_end,
                    node_end,
                    group_size,
                    path_edge_index=edge_index,
                )
            )

            cursor = edge_end

        schedule = PathSchedule(
            path=path,
            start_frame=int(start_frame),
            arrival_frame=cursor,
            intervals=intervals,
            first_departure_frame=first_departure_frame or int(start_frame),
            blocked_resource=first_blocked_resource,
        )

        return ScheduleAttempt(
            schedule=schedule,
            blocked_resource=first_blocked_resource,
            earliest_retry_frame=schedule.first_departure_frame,
            reason="ready" if schedule.first_departure_frame <= int(start_frame) else "future",
        )

    def find_earliest_feasible_schedule(
            self,
            path: list[Any],
            group_size: int,
            start_frame: int,
            *,
            horizon_edges: int | None = None,
            ignore_group_id: Any | None = None,
    ) -> PathSchedule | None:
        return self.attempt_earliest_feasible_schedule(
            path,
            group_size,
            start_frame,
            horizon_edges=horizon_edges,
            ignore_group_id=ignore_group_id,
        ).schedule

    def can_reserve_path(
        self,
        path: list[Any],
        group_size: int,
        start_frame: int,
        *,
        horizon_edges: int | None = None,
        ignore_group_id: Any | None = None,
    ) -> bool:
        return (
            self.find_earliest_feasible_schedule(
                path,
                group_size,
                start_frame,
                horizon_edges=horizon_edges,
                ignore_group_id=ignore_group_id,
            )
            is not None
        )

    def reserve_path(
        self,
        group_id: Any,
        path: list[Any],
        group_size: int,
        schedule: PathSchedule,
    ) -> bool:
        self.release_group(group_id)

        for interval in schedule.intervals:
            for bucket in range(interval.start_bucket, interval.end_bucket + 1):
                if not self._has_capacity(
                    interval.resource,
                    bucket,
                    interval.amount,
                    ignore_group_id=group_id,
                ):
                    return False

        for interval in schedule.intervals:
            for bucket in range(interval.start_bucket, interval.end_bucket + 1):
                self.reservations[interval.resource][bucket][group_id] = interval.amount

        self.group_reservations[group_id] = schedule
        return True

    def release_group(self, group_id: Any) -> None:
        self.remove_group_from_waiting_queues(group_id)

        schedule = self.group_reservations.pop(group_id, None)

        if schedule is None:
            return

        for interval in schedule.intervals:
            for bucket in range(interval.start_bucket, interval.end_bucket + 1):
                group_map = self.reservations.get(interval.resource, {}).get(bucket)
                if not group_map:
                    continue

                group_map.pop(group_id, None)

                if not group_map:
                    self.reservations[interval.resource].pop(bucket, None)

            if interval.resource in self.reservations and not self.reservations[interval.resource]:
                self.reservations.pop(interval.resource, None)

    def release_passed_resources(
            self,
            group_id: Any,
            current_node: Any,
            frame: int,
    ) -> None:
        schedule = self.group_reservations.get(group_id)

        if schedule is None:
            return

        current_index = -1

        if current_node in schedule.path:
            current_index = schedule.path.index(current_node)

        current_bucket = self.bucket_for_frame(frame)

        keep: list[ReservationInterval] = []

        for interval in schedule.intervals:
            expired = interval.end_bucket < current_bucket
            passed_by_node = (
                    current_index >= 0
                    and interval.path_edge_index is not None
                    and interval.path_edge_index < current_index
            )

            if expired or passed_by_node:
                for bucket in range(interval.start_bucket, interval.end_bucket + 1):
                    group_map = self.reservations.get(interval.resource, {}).get(bucket)

                    if group_map:
                        group_map.pop(group_id, None)
            else:
                keep.append(interval)

        schedule.intervals = keep

        if not keep:
            self.group_reservations.pop(group_id, None)

    def has_valid_next_reservation(
            self,
            group_id: Any,
            path: list[Any],
            current_node: Any,
            frame: int,
    ) -> bool:
        schedule = self.group_reservations.get(group_id)

        if schedule is None:
            return False

        if current_node not in path:
            return False

        idx = path.index(current_node)

        if idx >= len(path) - 1:
            return True

        next_edge = ("edge", path[idx], path[idx + 1])
        current_bucket = self.bucket_for_frame(frame)

        for interval in schedule.intervals:
            if interval.resource != next_edge:
                continue

            if interval.start_bucket <= current_bucket <= interval.end_bucket:
                return True

        return False

    def debug_resource_usage(
            self,
            resource: Resource,
            frame: int,
            *,
            window_buckets: int = 5,
            max_owners: int = 10,
    ) -> dict[str, Any]:
        current_bucket = self.bucket_for_frame(frame)
        capacity = self._resource_capacity(resource)

        buckets: dict[int, dict[str, Any]] = {}

        for bucket in range(current_bucket, current_bucket + window_buckets):
            group_map = self.reservations.get(resource, {}).get(bucket, {})

            owners = {
                str(group_id): amount
                for group_id, amount in list(group_map.items())[:max_owners]
            }

            buckets[bucket] = {
                "used": sum(group_map.values()),
                "capacity": capacity,
                "owners": owners,
                "owners_count": len(group_map),
            }

        return {
            "resource": resource,
            "frame": frame,
            "current_bucket": current_bucket,
            "capacity": capacity,
            "buckets": buckets,
        }

    def estimate_wait_time(
        self,
        resource: Resource,
        group_size: int,
        frame: int,
    ) -> int | None:
        start_bucket = self.bucket_for_frame(frame)

        for bucket in range(start_bucket, start_bucket + self.max_search_buckets + 1):
            if self._has_capacity(resource, bucket, group_size):
                return max(0, self._bucket_start_frame(bucket) - frame)

        return None

    def get_waiting_queue(self, resource: Resource) -> list[Any]:
        return [entry.group_id for entry in self.waiting_queues.get(resource, [])]

    def remove_group_from_waiting_queues(self, group_id: Any) -> None:
        for resource, queue in list(self.waiting_queues.items()):
            filtered_queue = [
                entry
                for entry in queue
                if entry.group_id != group_id
            ]

            if len(filtered_queue) == len(queue):
                continue

            heapq.heapify(filtered_queue)

            if filtered_queue:
                self.waiting_queues[resource] = filtered_queue
            else:
                self.waiting_queues.pop(resource, None)

    def enqueue_waiting_group(
            self,
            resource: Resource,
            group_id: Any,
            priority: float,
            *,
            frame: int = 0,
    ) -> None:
        self.remove_group_from_waiting_queues(group_id)

        heapq.heappush(
            self.waiting_queues[resource],
            QueueEntry(
                priority=float(priority),
                enqueued_frame=int(frame),
                group_id=group_id,
            ),
        )

    def dequeue_available_groups(
        self,
        resource: Resource,
        frame: int,
    ) -> list[Any]:
        queue = self.waiting_queues.get(resource)

        if not queue:
            return []

        available: list[Any] = []
        remaining: list[QueueEntry] = []

        while queue:
            entry = heapq.heappop(queue)
            wait_time = self.estimate_wait_time(resource, 1, frame)

            if wait_time == 0:
                available.append(entry.group_id)
            else:
                remaining.append(entry)

        for entry in remaining:
            heapq.heappush(queue, entry)

        return available

    def earliest_arrival_cost(
        self,
        path: list[Any],
        group_size: int,
        start_frame: int,
        *,
        horizon_edges: int | None = None,
        ignore_group_id: Any | None = None,
    ) -> float:
        schedule = self.find_earliest_feasible_schedule(
            path,
            group_size,
            start_frame,
            horizon_edges=horizon_edges,
            ignore_group_id=ignore_group_id,
        )

        if schedule is None:
            return float("inf")

        return float(schedule.arrival_frame - start_frame)


def get_capacity_reservation_manager(G: Any) -> CapacityReservationManager:
    manager = G.graph.get("capacity_reservation_manager")

    if isinstance(manager, CapacityReservationManager):
        return manager

    temporal_cfg = G.graph.get("temporal_capacity_config")

    bucket_size = max(1, int(getattr(temporal_cfg, "time_bucket_frames", 30)))
    horizon_frames = getattr(temporal_cfg, "temporal_horizon_frames", 900)
    traversal_time_scale = getattr(temporal_cfg, "traversal_time_scale", 1.0)
    node_capacity_default = getattr(temporal_cfg, "node_capacity_default", 20)
    edge_flow_capacity_default = getattr(temporal_cfg, "edge_flow_capacity_default", 10)

    manager = CapacityReservationManager(
        G,
        bucket_size_frames=bucket_size,
        max_search_buckets=max(1, int(math.ceil(horizon_frames / bucket_size))),
        traversal_time_scale=traversal_time_scale,
        node_capacity_default=node_capacity_default,
        edge_flow_capacity_default=edge_flow_capacity_default,
    )

    G.graph["capacity_reservation_manager"] = manager
    return manager


def reset_capacity_reservation_manager(G: Any) -> CapacityReservationManager:
    G.graph.pop("capacity_reservation_manager", None)
    return get_capacity_reservation_manager(G)