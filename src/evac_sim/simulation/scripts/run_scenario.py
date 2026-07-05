"""Run a validated scenario and produce structured JSON + CSV output.

Wraps the standard evac-sim runner and post-processes the resulting SQLite
databases into a single machine-readable JSON file suitable for integration
with external applications.

Examples
--------
    python -m evac_sim.simulation.scripts.run_scenario \\
        --config configs/management_building.yaml \\
        --scenario basement \\
        --output-dir results/api/basement \\
        --output-format json,csv

    python -m evac_sim.simulation.scripts.run_scenario \\
        --config configs/study.yaml \\
        --scenario corridor_case_1 \\
        --heuristic h1 \\
        --verbose
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_scenario",
        description="Run a validated scenario and write structured JSON/CSV output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--config",
        default="study.yaml",
        help="Config filename inside ./configs/ or absolute path (default: study.yaml).",
    )
    p.add_argument(
        "--scenario",
        default=None,
        help="Case/scenario key inside the YAML file.",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: ./runs/<timestamp>_<scenario>).",
    )
    p.add_argument(
        "--output-format",
        default="json,csv",
        help="Comma-separated list of output formats: json, csv (default: json,csv).",
    )
    p.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory).",
    )
    p.add_argument(
        "--heuristic",
        choices=["none", "h1", "h2", "h3"],
        default="none",
        help="Routing heuristic (default: none).",
    )
    p.add_argument(
        "--horizon-k",
        type=int,
        default=6,
        help="Reservation horizon for heuristic h2 (default: 6).",
    )
    p.add_argument(
        "--congestion-reroute-epsilon",
        type=float,
        default=0.1,
        help="Route improvement threshold for congestion rerouting (default: 0.1).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return p


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _read_trajectory(trajectory_db: Path) -> tuple[dict[int, list[dict]], int, float]:
    """Return (agent_frames, total_frames, fps).

    agent_frames maps agent_id → list of {frame, x, y}.
    """
    conn = sqlite3.connect(str(trajectory_db))
    try:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'fps'"
        ).fetchone()
        fps = float(row[0]) if row else 8.0

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        traj_table = next(
            (t for t in ("trajectory_data", "trajectory", "trajectories") if t in tables),
            None,
        )
        if traj_table is None:
            return {}, 0, fps

        rows = conn.execute(
            f"SELECT frame, id, pos_x, pos_y FROM {traj_table} ORDER BY id, frame"
        ).fetchall()
    finally:
        conn.close()

    agent_frames: dict[int, list[dict]] = {}
    total_frames = 0
    for frame, agent_id, x, y in rows:
        frame = int(frame)
        total_frames = max(total_frames, frame)
        agent_frames.setdefault(int(agent_id), []).append(
            {"frame": frame, "x": round(float(x), 4), "y": round(float(y), 4)}
        )
    return agent_frames, total_frames, fps


def _read_agent_areas(sim_db: Path, case_name: str, mode: int) -> dict[int, dict[int, str]]:
    """Return agent_id → {frame → node_id}."""
    conn = sqlite3.connect(str(sim_db))
    try:
        rows = conn.execute(
            """
            SELECT agent_id, frame, area
            FROM agent_area_data
            WHERE case_name = ? AND mode = ?
            ORDER BY agent_id, frame
            """,
            (case_name, mode),
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()

    result: dict[int, dict[int, str]] = {}
    for agent_id, frame, area in rows:
        result.setdefault(int(agent_id), {})[int(frame)] = str(area)
    return result


def _read_risks(sim_db: Path, case_name: str) -> list[dict]:
    conn = sqlite3.connect(str(sim_db))
    try:
        rows = conn.execute(
            """
            SELECT frame, area, risk_level
            FROM risk_data
            WHERE case_name = ?
            ORDER BY frame, area
            """,
            (case_name,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    return [
        {"frame": int(f), "node": str(a), "risk": round(float(r), 6)}
        for f, a, r in rows
    ]


def _read_metrics(sim_db: Path, case_name_mode: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(str(sim_db))
    try:
        exp_row = conn.execute(
            "SELECT id, source_nodes, agents_per_source FROM experiments WHERE case_name = ?",
            (case_name_mode,),
        ).fetchone()
        if exp_row is None:
            return None
        exp_id, src_json, agents_json = exp_row
        metrics_rows = conn.execute(
            """
            SELECT agent_group_id, algorithm, n_records, avg_time, median_time,
                   p90_time, min_time, max_time, cumulative_risk_exposure
            FROM experiment_metrics
            WHERE experiment_id = ?
            """,
            (exp_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

    groups = []
    total_evacuated = 0
    for row in metrics_rows:
        group_id, algo, n, avg, med, p90, mn, mx, risk_exp = row
        total_evacuated += int(n)
        groups.append({
            "group_id": str(group_id),
            "algorithm": algo,
            "n_evacuated": int(n),
            "avg_time": round(float(avg), 3),
            "median_time": round(float(med), 3),
            "p90_time": round(float(p90), 3),
            "min_time": round(float(mn), 3),
            "max_time": round(float(mx), 3),
            "cumulative_risk_exposure": round(float(risk_exp), 6),
        })

    import json as _json
    sources = _json.loads(src_json) if isinstance(src_json, str) else src_json
    agents_per_source = _json.loads(agents_json) if isinstance(agents_json, str) else agents_json
    total_agents = sum(int(a) for a in agents_per_source) if agents_per_source else 0

    return {
        "total_agents": total_agents,
        "evacuated_agents": total_evacuated,
        "not_evacuated_agents": total_agents - total_evacuated,
        "groups": groups,
    }


def _build_agent_records(
    *,
    agent_frames: dict[int, list[dict]],
    agent_areas: dict[int, dict[int, str]],
    total_frames: int,
    fps: float,
    sources: list,
    agents_per_source: list[int],
) -> list[dict]:
    # Map source → list of expected agent counts for labeling
    source_agent_map: list[tuple[str, int]] = []
    for src, n in zip(sources, agents_per_source):
        source_agent_map.append((str(src), int(n)))

    agent_list: list[dict] = []
    for agent_id, frames in sorted(agent_frames.items()):
        last_frame = frames[-1]["frame"] if frames else 0
        evacuated = last_frame < total_frames
        evac_time = round(last_frame / fps, 3) if fps > 0 else None

        areas = agent_areas.get(agent_id, {})
        trajectory = []
        for entry in frames:
            node = areas.get(entry["frame"], None)
            rec = {"frame": entry["frame"], "x": entry["x"], "y": entry["y"]}
            if node is not None:
                rec["node"] = node
            trajectory.append(rec)

        agent_list.append({
            "agent_id": agent_id,
            "evacuated": evacuated,
            "evacuation_time": evac_time,
            "trajectory": trajectory,
        })

    return agent_list


def _build_result_json(
    *,
    scenario_name: str,
    config: dict[str, Any],
    run_dir: Path,
    status: str,
    error_info: dict | None = None,
) -> dict[str, Any]:
    env_name: str = config.get("environment", "unknown")
    sources: list = config.get("sources") or []
    agents_per_source: list = config.get("agents") or []

    result: dict[str, Any] = {
        "scenario_name": scenario_name,
        "environment": env_name,
        "status": status,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "config": config,
    }

    if error_info:
        result["error"] = error_info
        result["summary"] = {}
        result["agents"] = []
        result["risks"] = []
        result["events"] = []
        result["diagnostics"] = {"blocked_agents": [], "congestion_points": [], "warnings": []}
        return result

    db_dir = run_dir / "artifacts" / "db"
    sim_db = db_dir / "simulation.db"

    # Detect trajectory files (one per mode)
    trajectory_files = sorted(db_dir.glob(f"{env_name}_mode_*.sqlite"))
    if not trajectory_files:
        trajectory_files = sorted(db_dir.glob("*_mode_*.sqlite"))

    all_agents: list[dict] = []
    all_risks: list[dict] = []
    summary_groups: list[dict] = []
    total_agents_global = 0
    evacuated_global = 0
    all_times: list[float] = []
    total_frames_global = 0

    for traj_file in trajectory_files:
        mode_str = traj_file.stem.split("_mode_")[-1]
        try:
            mode = int(mode_str)
        except ValueError:
            mode = 0

        case_name_mode = f"{scenario_name}_mode_{mode}"

        agent_frames, total_frames, fps = _read_trajectory(traj_file)
        total_frames_global = max(total_frames_global, total_frames)

        agent_areas = _read_agent_areas(sim_db, scenario_name, mode) if sim_db.exists() else {}

        agents = _build_agent_records(
            agent_frames=agent_frames,
            agent_areas=agent_areas,
            total_frames=total_frames,
            fps=fps,
            sources=sources,
            agents_per_source=[int(a) for a in agents_per_source],
        )

        for a in agents:
            a["mode"] = mode
        all_agents.extend(agents)

        metrics = _read_metrics(sim_db, case_name_mode) if sim_db.exists() else None
        if metrics:
            total_agents_global = max(total_agents_global, metrics["total_agents"])
            evacuated_global += metrics["evacuated_agents"]
            summary_groups.extend(metrics["groups"])
            for g in metrics["groups"]:
                all_times.append(g["avg_time"])

    if not all_risks and sim_db.exists():
        all_risks = _read_risks(sim_db, scenario_name)

    evac_times = [a["evacuation_time"] for a in all_agents if a.get("evacuation_time") is not None]

    summary: dict[str, Any] = {
        "total_agents": total_agents_global or sum(int(a) for a in agents_per_source),
        "evacuated_agents": evacuated_global,
        "not_evacuated_agents": max(0, (total_agents_global or 0) - evacuated_global),
        "evacuation_time": round(max(evac_times), 3) if evac_times else None,
        "average_evacuation_time": round(sum(evac_times) / len(evac_times), 3) if evac_times else None,
        "max_evacuation_time": round(max(evac_times), 3) if evac_times else None,
        "total_frames": total_frames_global,
        "groups": summary_groups,
    }

    result["summary"] = summary
    result["agents"] = all_agents
    result["risks"] = all_risks
    result["events"] = []
    result["diagnostics"] = {
        "blocked_agents": [],
        "congestion_points": [],
        "warnings": [],
    }

    return result


def _write_csv(result: dict[str, Any], output_dir: Path) -> None:
    agents = result.get("agents") or []
    if not agents:
        return

    csv_path = output_dir / "agents.csv"
    fieldnames = ["agent_id", "mode", "evacuated", "evacuation_time"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for a in agents:
            writer.writerow(a)

    summary = result.get("summary") or {}
    summary_path = output_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        for k, v in summary.items():
            if not isinstance(v, list):
                writer.writerow([k, v])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    output_formats = {fmt.strip().lower() for fmt in args.output_format.split(",")}

    # Resolve output dir if provided so we can write result.json there
    out_dir: Path | None = None
    if args.output_dir:
        out_dir = Path(args.output_dir)
        if not out_dir.is_absolute():
            out_dir = project_root / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)

    # Load config to get env name etc. for post-processing
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / "configs" / config_path
    if not config_path.exists():
        config_path = Path(args.config)

    cfg: dict[str, Any] = {}
    if config_path.exists() and args.scenario:
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            cfg = dict(raw.get(args.scenario, {}))
        except Exception:
            pass

    # Determine where the run will land (needed for post-processing)
    # run_from_yaml creates the dir internally; we pass out_dir to pin it.
    run_dir_for_postprocess: Path | None = None
    if out_dir is not None:
        run_dir_for_postprocess = out_dir

    status = "completed"
    error_info: dict | None = None

    try:
        from evac_sim.runner import run_from_yaml

        run_from_yaml(
            project_root=project_root,
            config_name=args.config if not Path(args.config).is_absolute() else str(config_path.relative_to(project_root / "configs")),
            case_id=args.scenario,
            out_dir=out_dir,
            verbose=args.verbose,
            heuristic=args.heuristic,
            horizon_k=args.horizon_k,
            congestion_reroute_epsilon=args.congestion_reroute_epsilon,
        )
    except Exception as exc:
        status = "failed"
        error_info = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        print(f"Simulation failed: {exc}", file=sys.stderr)

    # Use the output dir we passed; if none was given the runner created one
    # under runs/ — we can't know the exact name, so we skip post-processing.
    if run_dir_for_postprocess is None and status == "completed":
        print(
            "Note: no --output-dir was specified. "
            "result.json will not be written. Pass --output-dir to enable JSON export.",
            file=sys.stderr,
        )
        return 0

    if run_dir_for_postprocess is None:
        # Still write error JSON somewhere
        run_dir_for_postprocess = project_root / "runs" / "last_failed"
        run_dir_for_postprocess.mkdir(parents=True, exist_ok=True)

    result = _build_result_json(
        scenario_name=args.scenario or "unknown",
        config=cfg,
        run_dir=run_dir_for_postprocess,
        status=status,
        error_info=error_info,
    )

    if "json" in output_formats:
        json_path = run_dir_for_postprocess / "result.json"
        json_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"JSON result written to: {json_path}")

    if "csv" in output_formats:
        _write_csv(result, run_dir_for_postprocess)
        print(f"CSV files written to: {run_dir_for_postprocess}")

    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
