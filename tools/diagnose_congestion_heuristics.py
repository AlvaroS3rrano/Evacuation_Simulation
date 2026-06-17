from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CTX_RE = re.compile(r"frame=(?P<frame>\d+).*?group=(?P<group>[^|]+).*?agents=(?P<agents>\d+)")
BLOCKED_RESOURCE_RE = re.compile(
    r"blocked_resource=(?P<resource>.*?)(?: retry_frame=| wait_frames=| path=| movement_path=| remaining_path=| waiting_since=| reason=|$)"
)
QUEUE_RESOURCE_RE = re.compile(
    r"resource=(?P<resource>.*?)(?: priority=| queue_head=| movement_path=| waiting_resource=| reason=|$)"
)
CURRENT_NODE_RE = re.compile(r"current_node=(?P<node>.*?)(?: resource=| path_head=| blocked_resource=| movement_path=| remaining_path=| schedule=|$)")
PATH_HEAD_RE = re.compile(r"path_head=(?P<path>\[.*?\]|None)(?: waiting_resource=| reason=|$)")
MOVEMENT_PATH_RE = re.compile(r"movement_path=(?P<path>\[.*?\]|None)(?: usage=| schedule=|$)")
PRIORITY_RE = re.compile(r"priority=(?P<priority>-?\d+(?:\.\d+)?|inf|-inf|None)")
QUEUE_HEAD_RE = re.compile(r"queue_head=(?P<head>.*?)(?: movement_path=| waiting_resource=| reason=|$)")
MAX_FRAMES_RE = re.compile(r"Simulation stopped by max_frames .*? remaining_agents=(?P<remaining>\d+)")
SIM_END_RE = re.compile(r"Simulation end \| last_frame=(?P<frame>\d+)")


@dataclass
class GroupDiagnostics:
    group_id: str
    stopped_frames: list[int] = field(default_factory=list)
    resumed_frames: list[int] = field(default_factory=list)
    capacity_blocked_frames: list[int] = field(default_factory=list)
    capacity_ready_frames: list[int] = field(default_factory=list)
    capacity_pending_frames: list[int] = field(default_factory=list)
    queue_enqueue_frames: list[int] = field(default_factory=list)
    queue_wait_frames: list[int] = field(default_factory=list)
    future_reservation_frames: list[int] = field(default_factory=list)
    backtrack_frames: list[int] = field(default_factory=list)
    blocked_resources: dict[str, int] = field(default_factory=dict)
    queue_resources: dict[str, int] = field(default_factory=dict)
    queue_priorities: list[float] = field(default_factory=list)
    last_event: str | None = None
    last_frame: int | None = None
    last_current_node: str | None = None
    last_path_head: str | None = None
    last_movement_path: str | None = None
    last_queue_head: str | None = None

    @property
    def stopped_count(self) -> int:
        return len(self.stopped_frames)

    @property
    def resumed_count(self) -> int:
        return len(self.resumed_frames)

    @property
    def last_stopped_after_resume(self) -> bool:
        if not self.stopped_frames:
            return False
        if not self.resumed_frames:
            return True
        return max(self.stopped_frames) > max(self.resumed_frames)


@dataclass
class HeuristicDiagnostics:
    heuristic: str
    return_code: int
    duration_seconds: float
    out_dir: str
    log_file: str
    status: str = "PASS"
    reasons: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    top_blocked_resources: dict[str, int] = field(default_factory=dict)
    top_queue_resources: dict[str, int] = field(default_factory=dict)
    queue_checks: dict[str, Any] = field(default_factory=dict)
    evacuation_summary: dict[str, Any] = field(default_factory=dict)
    possible_stuck_groups: list[str] = field(default_factory=list)
    groups: dict[str, GroupDiagnostics] = field(default_factory=dict)
    db_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceCheck:
    name: str
    status: str
    path: str
    details: str


def _extract_ctx(line: str) -> tuple[int | None, str | None, int | None]:
    match = CTX_RE.search(line)
    if not match:
        return None, None, None
    return int(match.group("frame")), match.group("group").strip(), int(match.group("agents"))


def _normalise_optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value == "None":
        return None
    return value


def _extract_blocked_resource(line: str) -> str | None:
    match = BLOCKED_RESOURCE_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("resource"))


def _extract_queue_resource(line: str) -> str | None:
    match = QUEUE_RESOURCE_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("resource"))


def _extract_event_resource(line: str) -> str | None:
    return _extract_queue_resource(line) or _extract_blocked_resource(line)


def _extract_current_node(line: str) -> str | None:
    match = CURRENT_NODE_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("node"))


def _extract_path_head(line: str) -> str | None:
    match = PATH_HEAD_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("path"))


def _extract_movement_path(line: str) -> str | None:
    match = MOVEMENT_PATH_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("path"))


def _extract_priority(line: str) -> float | None:
    match = PRIORITY_RE.search(line)
    if not match:
        return None

    raw = match.group("priority")
    if raw == "None":
        return None

    try:
        return float(raw)
    except ValueError:
        return None


def _extract_queue_head(line: str) -> str | None:
    match = QUEUE_HEAD_RE.search(line)
    if not match:
        return None
    return _normalise_optional_value(match.group("head"))


def _event_name_for_line(line: str) -> str | None:
    if "Group stopped" in line:
        return "group_stopped"
    if "Group resumed" in line:
        return "group_resumed"
    if "Reroute backtrack detected" in line:
        return "reroute_backtrack"

    if "Capacity queue enqueue" in line:
        return "capacity_queue_enqueue"
    if "Capacity queue wait" in line:
        return "capacity_queue_wait"

    if "Capacity blocked" in line:
        return "capacity_blocked"
    if "Path capacity blocked" in line:
        return "path_capacity_blocked"
    if "Capacity future reservation skipped" in line:
        return "capacity_future_reservation_skipped"
    if "Path capacity future reservation skipped" in line:
        return "path_capacity_future_reservation_skipped"
    if "Capacity pending" in line:
        return "capacity_pending"
    if "Capacity ready" in line:
        return "capacity_ready"
    if "Capacity reservation race/failure" in line:
        return "capacity_race_failure"
    if "Path capacity reservation race/failure" in line:
        return "path_capacity_race_failure"
    if "Group waits due to no congestion-feasible path" in line:
        return "no_congestion_feasible_path"
    if "Group keeps waiting due to congestion" in line:
        return "keeps_waiting"
    if "Group enqueued" in line:
        return "group_enqueued"
    if "ERROR" in line or "Traceback" in line:
        return "error_or_traceback"
    return None


def _update_group_diagnostics(
    *,
    groups: dict[str, GroupDiagnostics],
    group_id: str,
    frame: int | None,
    event_name: str,
    line: str,
) -> None:
    diag = groups.setdefault(group_id, GroupDiagnostics(group_id=group_id))
    if frame is not None:
        diag.last_frame = frame

    current_node = _extract_current_node(line)
    if current_node is not None:
        diag.last_current_node = current_node

    path_head = _extract_path_head(line)
    if path_head is not None:
        diag.last_path_head = path_head

    movement_path = _extract_movement_path(line)
    if movement_path is not None:
        diag.last_movement_path = movement_path

    queue_head = _extract_queue_head(line)
    if queue_head is not None:
        diag.last_queue_head = queue_head

    blocked_resource = _extract_blocked_resource(line)
    if blocked_resource is not None:
        counter = Counter(diag.blocked_resources)
        counter[blocked_resource] += 1
        diag.blocked_resources = dict(counter)

    queue_resource = _extract_queue_resource(line)
    if queue_resource is not None:
        counter = Counter(diag.queue_resources)
        counter[queue_resource] += 1
        diag.queue_resources = dict(counter)

    priority = _extract_priority(line)
    if priority is not None:
        diag.queue_priorities.append(priority)

    if event_name == "group_stopped" and frame is not None:
        diag.stopped_frames.append(frame)
    elif event_name == "group_resumed" and frame is not None:
        diag.resumed_frames.append(frame)
    elif event_name in {"capacity_blocked", "path_capacity_blocked"} and frame is not None:
        diag.capacity_blocked_frames.append(frame)
    elif event_name == "capacity_ready" and frame is not None:
        diag.capacity_ready_frames.append(frame)
    elif event_name == "capacity_pending" and frame is not None:
        diag.capacity_pending_frames.append(frame)
    elif event_name == "capacity_queue_enqueue" and frame is not None:
        diag.queue_enqueue_frames.append(frame)
    elif event_name == "capacity_queue_wait" and frame is not None:
        diag.queue_wait_frames.append(frame)
    elif event_name in {"capacity_future_reservation_skipped", "path_capacity_future_reservation_skipped"} and frame is not None:
        diag.future_reservation_frames.append(frame)
    elif event_name == "reroute_backtrack" and frame is not None:
        diag.backtrack_frames.append(frame)

    diag.last_event = event_name


def _summarise_sqlite_db(db_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"path": str(db_path), "tables": {}}
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        summary["error"] = str(exc)
        return summary

    try:
        table_names = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ]
        for table in table_names:
            table_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            columns = [row[1] for row in table_info]
            table_summary: dict[str, Any] = {"columns": columns}
            try:
                table_summary["rows"] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                table_summary["rows"] = None
            if "frame" in columns:
                try:
                    table_summary["min_frame"] = conn.execute(f"SELECT MIN(frame) FROM {table}").fetchone()[0]
                    table_summary["max_frame"] = conn.execute(f"SELECT MAX(frame) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    pass
            for possible_agent_col in ("agent_id", "agent", "id_agent"):
                if possible_agent_col in columns:
                    try:
                        table_summary["distinct_agents"] = conn.execute(
                            f"SELECT COUNT(DISTINCT {possible_agent_col}) FROM {table}"
                        ).fetchone()[0]
                    except sqlite3.Error:
                        pass
                    break
            for possible_group_col in ("group_id", "group", "id_group"):
                if possible_group_col in columns:
                    try:
                        table_summary["distinct_groups"] = conn.execute(
                            f"SELECT COUNT(DISTINCT {possible_group_col}) FROM {table}"
                        ).fetchone()[0]
                    except sqlite3.Error:
                        pass
                    break
            summary["tables"][table] = table_summary
    finally:
        conn.close()
    return summary


def _summarise_dbs(out_dir: Path) -> dict[str, Any]:
    return {str(db_path): _summarise_sqlite_db(db_path) for db_path in sorted(out_dir.rglob("*.db"))}


def _weighted_average(
    rows: list[tuple[float | None, int | None]],
) -> float | None:
    total_weight = 0
    weighted_sum = 0.0

    for value, weight in rows:
        if value is None:
            continue

        safe_weight = int(weight or 1)
        if safe_weight <= 0:
            safe_weight = 1

        total_weight += safe_weight
        weighted_sum += float(value) * safe_weight

    if total_weight == 0:
        return None

    return weighted_sum / total_weight


def _summarise_evacuation_metrics(out_dir: Path) -> dict[str, Any]:
    """
    Read compact evacuation-time metrics from the run SQLite database.

    The terminal output uses this summary so the user can quickly see whether a
    run is progressing in a reasonable direction without opening the full report.
    """
    summaries: list[dict[str, Any]] = []

    for db_path in sorted(out_dir.rglob("*.db")):
        try:
            conn = sqlite3.connect(db_path)
        except sqlite3.Error as exc:
            summaries.append(
                {
                    "db_path": str(db_path),
                    "error": str(exc),
                }
            )
            continue

        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

            if "experiment_metrics" not in tables:
                summaries.append(
                    {
                        "db_path": str(db_path),
                        "error": "experiment_metrics table not found",
                    }
                )
                continue

            rows = conn.execute(
                """
                SELECT
                    COALESCE(n_records, 1),
                    avg_time,
                    median_time,
                    p90_time,
                    max_time,
                    min_time
                FROM experiment_metrics
                """
            ).fetchall()

            if not rows:
                summaries.append(
                    {
                        "db_path": str(db_path),
                        "error": "experiment_metrics table is empty",
                    }
                )
                continue

            n_records = [int(row[0] or 1) for row in rows]
            avg_rows = [(row[1], row[0]) for row in rows]
            median_rows = [(row[2], row[0]) for row in rows]
            p90_rows = [(row[3], row[0]) for row in rows]
            max_values = [row[4] for row in rows if row[4] is not None]
            min_values = [row[5] for row in rows if row[5] is not None]

            summaries.append(
                {
                    "db_path": str(db_path),
                    "groups": len(rows),
                    "total_records": sum(n_records),
                    "avg_time_weighted": _weighted_average(avg_rows),
                    "median_time_weighted": _weighted_average(median_rows),
                    "p90_time_weighted": _weighted_average(p90_rows),
                    "max_time": max(max_values) if max_values else None,
                    "min_time": min(min_values) if min_values else None,
                }
            )

        except sqlite3.Error as exc:
            summaries.append(
                {
                    "db_path": str(db_path),
                    "error": str(exc),
                }
            )
        finally:
            conn.close()

    if not summaries:
        return {}

    valid_summaries = [
        summary
        for summary in summaries
        if "error" not in summary
    ]

    if not valid_summaries:
        return {
            "databases": summaries,
        }

    total_records = sum(int(summary.get("total_records", 0)) for summary in valid_summaries)
    avg_time_weighted = _weighted_average(
        [
            (summary.get("avg_time_weighted"), summary.get("total_records", 1))
            for summary in valid_summaries
        ]
    )
    median_time_weighted = _weighted_average(
        [
            (summary.get("median_time_weighted"), summary.get("total_records", 1))
            for summary in valid_summaries
        ]
    )
    p90_time_weighted = _weighted_average(
        [
            (summary.get("p90_time_weighted"), summary.get("total_records", 1))
            for summary in valid_summaries
        ]
    )

    return {
        "groups": sum(int(summary.get("groups", 0)) for summary in valid_summaries),
        "total_records": total_records,
        "avg_time_weighted": avg_time_weighted,
        "median_time_weighted": median_time_weighted,
        "p90_time_weighted": p90_time_weighted,
        "max_time": max(
            summary["max_time"]
            for summary in valid_summaries
            if summary.get("max_time") is not None
        ),
        "min_time": min(
            summary["min_time"]
            for summary in valid_summaries
            if summary.get("min_time") is not None
        ),
        "databases": summaries,
    }


def _format_seconds(value: float | int | None) -> str:
    if value is None:
        return "-"

    return f"{float(value):.2f}s"


def _format_evacuation_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return "evac_avg=- evac_p90=- evac_max=-"

    return (
        "evac_avg={avg} evac_p90={p90} evac_max={max_time}".format(
            avg=_format_seconds(summary.get("avg_time_weighted")),
            p90=_format_seconds(summary.get("p90_time_weighted")),
            max_time=_format_seconds(summary.get("max_time")),
        )
    )


def _queue_checks_for_log(*, counts: Counter[str], lines: list[str]) -> dict[str, Any]:
    queue_event_lines = [
        line for line in lines if "Capacity queue enqueue" in line or "Capacity queue wait" in line
    ]

    missing_priority = 0
    missing_queue_head = 0
    queue_wait_where_group_is_head = 0
    queue_events_with_nonzero_priority = 0
    queue_events_with_negative_priority = 0

    queue_resource_counter: Counter[str] = Counter()

    for line in queue_event_lines:
        priority = _extract_priority(line)
        queue_head = _extract_queue_head(line)
        resource = _extract_queue_resource(line)
        frame, group_id, _agents = _extract_ctx(line)

        if priority is None:
            missing_priority += 1
        else:
            if priority != 0:
                queue_events_with_nonzero_priority += 1
            if priority < 0:
                queue_events_with_negative_priority += 1

        if queue_head is None:
            missing_queue_head += 1

        if "Capacity queue wait" in line and group_id is not None and queue_head == group_id:
            queue_wait_where_group_is_head += 1

        if resource is not None:
            queue_resource_counter[resource] += 1

    return {
        "queue_events": len(queue_event_lines),
        "queue_enqueue": counts.get("capacity_queue_enqueue", 0),
        "queue_wait": counts.get("capacity_queue_wait", 0),
        "missing_priority": missing_priority,
        "missing_queue_head": missing_queue_head,
        "queue_wait_where_group_is_head": queue_wait_where_group_is_head,
        "queue_events_with_nonzero_priority": queue_events_with_nonzero_priority,
        "queue_events_with_negative_priority": queue_events_with_negative_priority,
        "top_queue_resources": dict(queue_resource_counter.most_common(10)),
    }


def analyse_log(
    *,
    heuristic: str,
    return_code: int,
    duration_seconds: float,
    out_dir: Path,
    log_file: Path,
) -> HeuristicDiagnostics:
    text = log_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    counts: Counter[str] = Counter()
    blocked_resources: Counter[str] = Counter()
    queue_resources: Counter[str] = Counter()
    groups: dict[str, GroupDiagnostics] = {}
    max_frames_remaining_agents: int | None = None
    simulation_end_frame: int | None = None

    for line in lines:
        max_match = MAX_FRAMES_RE.search(line)
        if max_match:
            counts["max_frames_stop"] += 1
            max_frames_remaining_agents = int(max_match.group("remaining"))

        end_match = SIM_END_RE.search(line)
        if end_match:
            simulation_end_frame = int(end_match.group("frame"))

        event_name = _event_name_for_line(line)
        if event_name is None:
            continue

        counts[event_name] += 1

        resource = _extract_blocked_resource(line)
        if resource is not None:
            blocked_resources[resource] += 1

        queue_resource = _extract_queue_resource(line)
        if queue_resource is not None:
            queue_resources[queue_resource] += 1

        frame, group_id, _agents = _extract_ctx(line)
        if group_id is not None:
            _update_group_diagnostics(
                groups=groups,
                group_id=group_id,
                frame=frame,
                event_name=event_name,
                line=line,
            )

    queue_checks = _queue_checks_for_log(counts=counts, lines=lines)

    possible_stuck_groups = sorted(
        group_id for group_id, diag in groups.items() if diag.last_stopped_after_resume
    )

    result = HeuristicDiagnostics(
        heuristic=heuristic,
        return_code=return_code,
        duration_seconds=duration_seconds,
        out_dir=str(out_dir),
        log_file=str(log_file),
        counts=dict(counts),
        top_blocked_resources=dict(blocked_resources.most_common(10)),
        top_queue_resources=dict(queue_resources.most_common(10)),
        queue_checks=queue_checks,
        evacuation_summary=_summarise_evacuation_metrics(out_dir),
        possible_stuck_groups=possible_stuck_groups,
        groups=groups,
        db_summary=_summarise_dbs(out_dir),
    )

    if return_code != 0:
        result.status = "FAIL"
        result.reasons.append(f"Command returned non-zero exit code: {return_code}")
    if counts["error_or_traceback"] > 0:
        result.status = "FAIL"
        result.reasons.append("Log contains ERROR or Traceback lines.")
    if counts["max_frames_stop"] > 0:
        result.status = "FAIL"
        result.reasons.append(
            f"Simulation hit max_frames with remaining_agents={max_frames_remaining_agents}."
        )
    if heuristic != "none" and counts["group_stopped"] > 0 and counts["group_resumed"] == 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append("Groups stopped due to capacity but no Group resumed event was observed.")
    if heuristic != "none" and possible_stuck_groups:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append(f"{len(possible_stuck_groups)} groups appear stopped after their last resume.")
    if counts["reroute_backtrack"] > 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append(f"{counts['reroute_backtrack']} reroute backtrack events detected.")
    if heuristic != "none" and counts["capacity_race_failure"] + counts["path_capacity_race_failure"] > 0:
        result.status = "FAIL"
        result.reasons.append("Capacity reservation race/failure detected.")
    if heuristic != "none" and queue_checks["queue_wait_where_group_is_head"] > 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append(
            f"{queue_checks['queue_wait_where_group_is_head']} queue-wait events had the same group as queue head."
        )
    if heuristic != "none" and queue_checks["missing_priority"] > 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append(f"{queue_checks['missing_priority']} queue events did not expose a priority value.")
    if heuristic != "none" and (
        counts["capacity_blocked"] + counts["path_capacity_blocked"] > 0
        and queue_checks["queue_enqueue"] == 0
    ):
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append("Capacity blocks occurred but no spatial queue enqueue event was observed.")
    if simulation_end_frame is None and return_code == 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append("Simulation end frame was not found in the log.")
    if not result.reasons:
        result.reasons.append("No critical diagnostic issue detected.")

    return result


def run_source_checks(project_root: Path) -> list[SourceCheck]:
    checks: list[SourceCheck] = []

    capacity_path = project_root / "src" / "evac_sim" / "simulation" / "capacity_reservations.py"
    group_processing_path = project_root / "src" / "evac_sim" / "simulation" / "group_processing.py"

    def add_check(name: str, status: str, path: Path, details: str) -> None:
        checks.append(
            SourceCheck(
                name=name,
                status=status,
                path=str(path),
                details=details,
            )
        )

    if not capacity_path.exists():
        add_check(
            "capacity_reservations.py exists",
            "FAIL",
            capacity_path,
            "File not found.",
        )
    else:
        capacity_text = capacity_path.read_text(encoding="utf-8", errors="replace")
        expected_capacity_tokens = {
            "QueueEntry stores group_size": "group_size: int",
            "enqueue_waiting_group accepts group_size": "group_size: int = 1",
            "queue head helper exists": "first_waiting_group",
            "queue wait helper exists": "should_group_wait_for_queue",
            "dequeue uses real group size": "entry.group_size",
        }

        for name, token in expected_capacity_tokens.items():
            add_check(
                name,
                "PASS" if token in capacity_text else "FAIL",
                capacity_path,
                f"Expected token `{token}` {'found' if token in capacity_text else 'not found'}.",
            )

    if not group_processing_path.exists():
        add_check(
            "group_processing.py exists",
            "FAIL",
            group_processing_path,
            "File not found.",
        )
    else:
        group_processing_text = group_processing_path.read_text(encoding="utf-8", errors="replace")
        expected_group_processing_tokens = {
            "movement resource helper exists": "_movement_resources",
            "spatial priority helper exists": "_waiting_priority_for_resource",
            "spatial enqueue helper exists": "_enqueue_with_spatial_priority",
            "queue wait log exists": "Capacity queue wait",
            "queue enqueue log exists": "Capacity queue enqueue",
            "queue check blocks non-head groups": "should_group_wait_for_queue",
        }

        for name, token in expected_group_processing_tokens.items():
            add_check(
                name,
                "PASS" if token in group_processing_text else "FAIL",
                group_processing_path,
                f"Expected token `{token}` {'found' if token in group_processing_text else 'not found'}.",
            )

    return checks


def _format_counter_map(counter_map: dict[str, int], *, limit: int = 8) -> str:
    if not counter_map:
        return "-"
    return ", ".join(f"{key}: {value}" for key, value in list(counter_map.items())[:limit])


def _format_source_check_status(checks: list[SourceCheck]) -> str:
    if not checks:
        return "SKIPPED"
    if any(check.status == "FAIL" for check in checks):
        return "FAIL"
    if any(check.status == "WARN" for check in checks):
        return "WARN"
    return "PASS"


def write_markdown_report(
    *,
    report_path: Path,
    diagnostics: list[HeuristicDiagnostics],
    source_checks: list[SourceCheck],
) -> None:
    lines: list[str] = []
    lines.append("# Congestion heuristic diagnostics")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Heuristic | Status | Runtime (s) | Evac avg | Evac p90 | Evac max | Stopped | Resumed | Ready | Blocked | Pending | Queue enqueue | Queue wait | Backtracks | Stuck groups | Main reason |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for diag in diagnostics:
        counts = diag.counts
        reason = diag.reasons[0] if diag.reasons else ""
        lines.append(
            "| {heuristic} | {status} | {duration:.2f} | {evac_avg} | {evac_p90} | {evac_max} | {stopped} | {resumed} | {ready} | {blocked} | {pending} | {queue_enqueue} | {queue_wait} | {backtracks} | {stuck} | {reason} |".format(
                heuristic=diag.heuristic,
                status=diag.status,
                duration=diag.duration_seconds,
                evac_avg=_format_seconds(diag.evacuation_summary.get("avg_time_weighted")),
                evac_p90=_format_seconds(diag.evacuation_summary.get("p90_time_weighted")),
                evac_max=_format_seconds(diag.evacuation_summary.get("max_time")),
                stopped=counts.get("group_stopped", 0),
                resumed=counts.get("group_resumed", 0),
                ready=counts.get("capacity_ready", 0),
                blocked=counts.get("capacity_blocked", 0) + counts.get("path_capacity_blocked", 0),
                pending=counts.get("capacity_pending", 0),
                queue_enqueue=counts.get("capacity_queue_enqueue", 0),
                queue_wait=counts.get("capacity_queue_wait", 0),
                backtracks=counts.get("reroute_backtrack", 0),
                stuck=len(diag.possible_stuck_groups),
                reason=reason.replace("|", "\\|"),
            )
        )

    lines.append("")
    lines.append("## Source checks")
    lines.append("")
    lines.append(f"Overall source-check status: **{_format_source_check_status(source_checks)}**")
    lines.append("")
    if source_checks:
        lines.append("| Check | Status | Path | Details |")
        lines.append("|---|---:|---|---|")
        for check in source_checks:
            lines.append(
                "| {name} | {status} | `{path}` | {details} |".format(
                    name=check.name.replace("|", "\\|"),
                    status=check.status,
                    path=check.path,
                    details=check.details.replace("|", "\\|"),
                )
            )
    else:
        lines.append("Source checks were skipped.")

    lines.append("")
    lines.append("## Details by heuristic")
    lines.append("")

    for diag in diagnostics:
        lines.append(f"### {diag.heuristic}")
        lines.append("")
        lines.append(f"- **Status:** {diag.status}")
        lines.append(f"- **Log:** `{diag.log_file}`")
        lines.append(f"- **Output dir:** `{diag.out_dir}`")
        lines.append(f"- **Return code:** {diag.return_code}")
        lines.append(f"- **Runtime:** {diag.duration_seconds:.2f} s")
        lines.append(f"- **Evacuation summary:** `{json.dumps(diag.evacuation_summary, ensure_ascii=False)}`")
        lines.append(f"- **Reasons:** {'; '.join(diag.reasons)}")
        lines.append(f"- **Counts:** `{json.dumps(diag.counts, ensure_ascii=False)}`")
        lines.append(f"- **Queue checks:** `{json.dumps(diag.queue_checks, ensure_ascii=False)}`")
        lines.append(f"- **Top blocked resources:** {_format_counter_map(diag.top_blocked_resources)}")
        lines.append(f"- **Top queue resources:** {_format_counter_map(diag.top_queue_resources)}")
        if diag.possible_stuck_groups:
            lines.append(f"- **Possible stuck groups:** {', '.join(diag.possible_stuck_groups[:25])}")
        else:
            lines.append("- **Possible stuck groups:** -")

        suspicious_groups = [
            group
            for group in diag.groups.values()
            if (
                group.last_stopped_after_resume
                or group.backtrack_frames
                or group.queue_wait_frames
                or group.queue_enqueue_frames
            )
        ]
        if suspicious_groups:
            lines.append("")
            lines.append("| Group | Last frame | Stopped | Resumed | Ready | Queue enqueue | Queue wait | Backtracks | Last node | Last event | Last path | Last movement | Last queue head | Blocked resources | Queue resources |")
            lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|")
            for group in sorted(
                suspicious_groups,
                key=lambda g: (g.last_frame if g.last_frame is not None else -1, g.group_id),
                reverse=True,
            )[:40]:
                lines.append(
                    "| {group_id} | {last_frame} | {stopped} | {resumed} | {ready} | {queue_enqueue} | {queue_wait} | {backtracks} | {last_node} | {last_event} | `{path}` | `{movement}` | {queue_head} | {blocked_resources} | {queue_resources} |".format(
                        group_id=group.group_id,
                        last_frame=group.last_frame,
                        stopped=group.stopped_count,
                        resumed=group.resumed_count,
                        ready=len(group.capacity_ready_frames),
                        queue_enqueue=len(group.queue_enqueue_frames),
                        queue_wait=len(group.queue_wait_frames),
                        backtracks=len(group.backtrack_frames),
                        last_node=group.last_current_node,
                        last_event=group.last_event,
                        path=(group.last_path_head or "-").replace("|", "\\|"),
                        movement=(group.last_movement_path or "-").replace("|", "\\|"),
                        queue_head=group.last_queue_head or "-",
                        blocked_resources=_format_counter_map(group.blocked_resources, limit=3).replace("|", "\\|"),
                        queue_resources=_format_counter_map(group.queue_resources, limit=3).replace("|", "\\|"),
                    )
                )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_heuristic(
    *,
    heuristic: str,
    config: str,
    case: str,
    out_root: Path,
    verbose: bool,
    extra_args: list[str],
) -> HeuristicDiagnostics:
    run_dir = out_root / f"{case}_{heuristic}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_root / f"{case}_{heuristic}.log"

    cli_args = [
        "run",
        "--config", config,
        "--case", case,
        "--heuristic", heuristic,
        "--out-dir", str(run_dir),
    ]
    if verbose:
        cli_args.append("-v")
    cli_args.extend(extra_args)

    code = "from evac_sim.cli import main; " f"main({cli_args!r})"
    command = [sys.executable, "-c", code]

    start = time.perf_counter()
    with log_file.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(command)}\n")
        log.write(f"CLI args: {cli_args!r}\n\n")
        log.flush()
        completed = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    duration = time.perf_counter() - start

    return analyse_log(
        heuristic=heuristic,
        return_code=completed.returncode,
        duration_seconds=duration,
        out_dir=run_dir,
        log_file=log_file,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run congestion heuristics and produce diagnostics from logs."
    )
    parser.add_argument("--config", default="congestion_heuristics.yaml")
    parser.add_argument("--case", default="congestion_two_exits")
    parser.add_argument("--heuristics", nargs="+", default=["none", "h1", "h2", "h3"])
    parser.add_argument("--out-root", default="./runs/diagnostics_congestion")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("-v", "--verbose", action="store_true", help="Pass -v to evac_sim.cli.")
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra CLI argument passed to evac_sim. Use multiple times.",
    )
    parser.add_argument(
        "--skip-source-checks",
        action="store_true",
        help="Skip static source checks for the spatial waiting queue implementation.",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Kept for backwards compatibility. Progress is now always shown as compact RUN/OK/FAIL lines.",
    )
    return parser.parse_args()


def _status_symbol(status: str) -> str:
    if status == "PASS":
        return "OK"
    if status == "WARN":
        return "WARN"
    return "FAIL"


def _run_started_line(
    *,
    run_number: int,
    total_runs: int,
    case: str,
    heuristic: str,
    out_root: Path,
) -> str:
    return (
        "[{current}/{total}] RUN  case={case} heuristic={heuristic} "
        "out={out}".format(
            current=run_number,
            total=total_runs,
            case=case,
            heuristic=heuristic,
            out=out_root / f"{case}_{heuristic}",
        )
    )


def _run_finished_line(
    *,
    run_number: int,
    total_runs: int,
    case: str,
    diag: HeuristicDiagnostics,
) -> str:
    counts = diag.counts
    return (
        "[{current}/{total}] {status:<4} case={case} heuristic={heuristic} "
        "runtime={runtime:.2f}s {evac} stopped={stopped} resumed={resumed} "
        "blocked={blocked} pending={pending} stuck={stuck}".format(
            current=run_number,
            total=total_runs,
            status=_status_symbol(diag.status),
            case=case,
            heuristic=diag.heuristic,
            runtime=diag.duration_seconds,
            evac=_format_evacuation_summary(diag.evacuation_summary),
            stopped=counts.get("group_stopped", 0),
            resumed=counts.get("group_resumed", 0),
            blocked=counts.get("capacity_blocked", 0) + counts.get("path_capacity_blocked", 0),
            pending=counts.get("capacity_pending", 0),
            stuck=len(diag.possible_stuck_groups),
        )
    )


def _terminal_summary(
    *,
    diagnostics: list[HeuristicDiagnostics],
    json_report: Path,
    md_report: Path,
    source_checks_report: Path,
    source_checks: list[SourceCheck],
) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append("Diagnostics finished.")
    lines.append(f"Source checks: {_format_source_check_status(source_checks)}")
    lines.append("")
    lines.append("Reports generated:")
    lines.append(f"- {json_report}")
    lines.append(f"- {md_report}")
    lines.append(f"- {source_checks_report}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    project_root = Path(args.project_root)

    source_checks: list[SourceCheck] = []
    if not args.skip_source_checks:
        source_checks = run_source_checks(project_root)

    diagnostics: list[HeuristicDiagnostics] = []

    total_runs = len(args.heuristics)

    for run_number, heuristic in enumerate(args.heuristics, start=1):
        print(
            _run_started_line(
                run_number=run_number,
                total_runs=total_runs,
                case=args.case,
                heuristic=heuristic,
                out_root=out_root,
            ),
            flush=True,
        )

        diag = run_heuristic(
            heuristic=heuristic,
            config=args.config,
            case=args.case,
            out_root=out_root,
            verbose=args.verbose,
            extra_args=args.extra_arg,
        )
        diagnostics.append(diag)

        print(
            _run_finished_line(
                run_number=run_number,
                total_runs=total_runs,
                case=args.case,
                diag=diag,
            ),
            flush=True,
        )

        if diag.status == "FAIL":
            for reason in diag.reasons[:3]:
                print(f"      reason: {reason}", flush=True)

    json_report = out_root / "diagnostics_report.json"
    md_report = out_root / "diagnostics_report.md"
    source_checks_report = out_root / "source_checks.json"

    serialisable = [
        {
            **asdict(diag),
            "groups": {
                group_id: asdict(group_diag)
                for group_id, group_diag in diag.groups.items()
            },
        }
        for diag in diagnostics
    ]

    json_report.write_text(
        json.dumps(serialisable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    source_checks_report.write_text(
        json.dumps([asdict(check) for check in source_checks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown_report(
        report_path=md_report,
        diagnostics=diagnostics,
        source_checks=source_checks,
    )

    print(
        _terminal_summary(
            diagnostics=diagnostics,
            json_report=json_report,
            md_report=md_report,
            source_checks_report=source_checks_report,
            source_checks=source_checks,
        )
    )


if __name__ == "__main__":
    main()
