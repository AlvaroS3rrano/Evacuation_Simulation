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
    r"blocked_resource=(?P<resource>.*?)(?: retry_frame=| wait_frames=| path=| remaining_path=| waiting_since=| reason=|$)"
)
CURRENT_NODE_RE = re.compile(r"current_node=(?P<node>.*?)(?: path_head=| blocked_resource=| remaining_path=| schedule=|$)")
PATH_HEAD_RE = re.compile(r"path_head=(?P<path>\[.*?\]|None)(?: waiting_resource=| reason=|$)")
MAX_FRAMES_RE = re.compile(r"Simulation stopped by max_frames .*? remaining_agents=(?P<remaining>\d+)")
SIM_END_RE = re.compile(r"Simulation end \| last_frame=(?P<frame>\d+)")


@dataclass
class GroupDiagnostics:
    group_id: str
    stopped_frames: list[int] = field(default_factory=list)
    resumed_frames: list[int] = field(default_factory=list)
    capacity_blocked_frames: list[int] = field(default_factory=list)
    future_reservation_frames: list[int] = field(default_factory=list)
    backtrack_frames: list[int] = field(default_factory=list)
    blocked_resources: dict[str, int] = field(default_factory=dict)
    last_event: str | None = None
    last_frame: int | None = None
    last_current_node: str | None = None
    last_path_head: str | None = None

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
    possible_stuck_groups: list[str] = field(default_factory=list)
    groups: dict[str, GroupDiagnostics] = field(default_factory=dict)
    db_summary: dict[str, Any] = field(default_factory=dict)


def _extract_ctx(line: str) -> tuple[int | None, str | None, int | None]:
    match = CTX_RE.search(line)
    if not match:
        return None, None, None
    return int(match.group("frame")), match.group("group").strip(), int(match.group("agents"))


def _extract_blocked_resource(line: str) -> str | None:
    match = BLOCKED_RESOURCE_RE.search(line)
    if not match:
        return None
    resource = match.group("resource").strip()
    if not resource or resource == "None":
        return None
    return resource


def _extract_current_node(line: str) -> str | None:
    match = CURRENT_NODE_RE.search(line)
    if not match:
        return None
    node = match.group("node").strip()
    if not node or node == "None":
        return None
    return node


def _extract_path_head(line: str) -> str | None:
    match = PATH_HEAD_RE.search(line)
    if not match:
        return None
    path = match.group("path").strip()
    if not path or path == "None":
        return None
    return path


def _event_name_for_line(line: str) -> str | None:
    if "Group stopped" in line:
        return "group_stopped"
    if "Group resumed" in line:
        return "group_resumed"
    if "Reroute backtrack detected" in line:
        return "reroute_backtrack"
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

    blocked_resource = _extract_blocked_resource(line)
    if blocked_resource is not None:
        counter = Counter(diag.blocked_resources)
        counter[blocked_resource] += 1
        diag.blocked_resources = dict(counter)

    if event_name == "group_stopped" and frame is not None:
        diag.stopped_frames.append(frame)
    elif event_name == "group_resumed" and frame is not None:
        diag.resumed_frames.append(frame)
    elif event_name in {"capacity_blocked", "path_capacity_blocked"} and frame is not None:
        diag.capacity_blocked_frames.append(frame)
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


def analyse_log(
    *,
    heuristic: str,
    return_code: int,
    duration_seconds: float,
    out_dir: Path,
    log_file: Path,
) -> HeuristicDiagnostics:
    text = log_file.read_text(encoding="utf-8", errors="replace")
    counts: Counter[str] = Counter()
    blocked_resources: Counter[str] = Counter()
    groups: dict[str, GroupDiagnostics] = {}
    max_frames_remaining_agents: int | None = None
    simulation_end_frame: int | None = None

    for line in text.splitlines():
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

        frame, group_id, _agents = _extract_ctx(line)
        if group_id is not None:
            _update_group_diagnostics(
                groups=groups,
                group_id=group_id,
                frame=frame,
                event_name=event_name,
                line=line,
            )

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
    if simulation_end_frame is None and return_code == 0:
        if result.status != "FAIL":
            result.status = "WARN"
        result.reasons.append("Simulation end frame was not found in the log.")
    if not result.reasons:
        result.reasons.append("No critical diagnostic issue detected.")

    return result


def _format_counter_map(counter_map: dict[str, int], *, limit: int = 8) -> str:
    if not counter_map:
        return "-"
    return ", ".join(f"{key}: {value}" for key, value in list(counter_map.items())[:limit])


def write_markdown_report(*, report_path: Path, diagnostics: list[HeuristicDiagnostics]) -> None:
    lines: list[str] = []
    lines.append("# Congestion heuristic diagnostics")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Heuristic | Status | Duration (s) | Stopped | Resumed | Blocked | Pending | Future skipped | Backtracks | Stuck groups | Main reason |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for diag in diagnostics:
        counts = diag.counts
        reason = diag.reasons[0] if diag.reasons else ""
        lines.append(
            "| {heuristic} | {status} | {duration:.2f} | {stopped} | {resumed} | {blocked} | {pending} | {future} | {backtracks} | {stuck} | {reason} |".format(
                heuristic=diag.heuristic,
                status=diag.status,
                duration=diag.duration_seconds,
                stopped=counts.get("group_stopped", 0),
                resumed=counts.get("group_resumed", 0),
                blocked=counts.get("capacity_blocked", 0) + counts.get("path_capacity_blocked", 0),
                pending=counts.get("capacity_pending", 0),
                future=counts.get("capacity_future_reservation_skipped", 0)
                + counts.get("path_capacity_future_reservation_skipped", 0),
                backtracks=counts.get("reroute_backtrack", 0),
                stuck=len(diag.possible_stuck_groups),
                reason=reason.replace("|", "\\|"),
            )
        )

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
        lines.append(f"- **Duration:** {diag.duration_seconds:.2f} s")
        lines.append(f"- **Reasons:** {'; '.join(diag.reasons)}")
        lines.append(f"- **Counts:** `{json.dumps(diag.counts, ensure_ascii=False)}`")
        lines.append(f"- **Top blocked resources:** {_format_counter_map(diag.top_blocked_resources)}")
        if diag.possible_stuck_groups:
            lines.append(f"- **Possible stuck groups:** {', '.join(diag.possible_stuck_groups[:25])}")
        else:
            lines.append("- **Possible stuck groups:** -")

        suspicious_groups = [
            group for group in diag.groups.values() if group.last_stopped_after_resume or group.backtrack_frames
        ]
        if suspicious_groups:
            lines.append("")
            lines.append("| Group | Last frame | Stopped | Resumed | Backtracks | Last node | Last event | Last path head | Blocked resources |")
            lines.append("|---|---:|---:|---:|---:|---|---|---|---|")
            for group in sorted(
                suspicious_groups,
                key=lambda g: (g.last_frame if g.last_frame is not None else -1, g.group_id),
                reverse=True,
            )[:30]:
                lines.append(
                    "| {group_id} | {last_frame} | {stopped} | {resumed} | {backtracks} | {last_node} | {last_event} | `{path}` | {resources} |".format(
                        group_id=group.group_id,
                        last_frame=group.last_frame,
                        stopped=group.stopped_count,
                        resumed=group.resumed_count,
                        backtracks=len(group.backtrack_frames),
                        last_node=group.last_current_node,
                        last_event=group.last_event,
                        path=(group.last_path_head or "-").replace("|", "\\|"),
                        resources=_format_counter_map(group.blocked_resources, limit=4).replace("|", "\\|"),
                    )
                )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_heuristic(
    *,
    heuristic: str,
    config: str,
    case: str,
    beta: str,
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
        "--beta", beta,
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
    parser.add_argument("--heuristics", nargs="+", default=["h1"]) # ["none", "h1", "h2", "h3"]
    parser.add_argument("--beta", default="1.0")
    parser.add_argument("--out-root", default="./runs/diagnostics_congestion")
    parser.add_argument("-v", "--verbose", action="store_true", help="Pass -v to evac_sim.cli.")
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra CLI argument passed to evac_sim. Use multiple times.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    diagnostics: list[HeuristicDiagnostics] = []

    for heuristic in args.heuristics:
        print(f"\n=== Running heuristic: {heuristic} ===")
        diag = run_heuristic(
            heuristic=heuristic,
            config=args.config,
            case=args.case,
            beta=args.beta,
            out_root=out_root,
            verbose=args.verbose,
            extra_args=args.extra_arg,
        )
        diagnostics.append(diag)
        print(
            f"{heuristic}: {diag.status} | stopped={diag.counts.get('group_stopped', 0)} "
            f"resumed={diag.counts.get('group_resumed', 0)} "
            f"blocked={diag.counts.get('capacity_blocked', 0) + diag.counts.get('path_capacity_blocked', 0)} "
            f"future_skipped={diag.counts.get('capacity_future_reservation_skipped', 0) + diag.counts.get('path_capacity_future_reservation_skipped', 0)} "
            f"backtracks={diag.counts.get('reroute_backtrack', 0)} "
            f"stuck_groups={len(diag.possible_stuck_groups)}"
        )
        for reason in diag.reasons:
            print(f"  - {reason}")

    json_report = out_root / "diagnostics_report.json"
    md_report = out_root / "diagnostics_report.md"

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
    write_markdown_report(report_path=md_report, diagnostics=diagnostics)
    write_markdown_report(report_path=md_report, diagnostics=diagnostics)

    print("\nReports generated:")
    print(f"- {json_report}")
    print(f"- {md_report}")


if __name__ == "__main__":
    main()
