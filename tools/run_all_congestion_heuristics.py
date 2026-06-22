from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evac_sim.cli import main  # noqa: E402


DEFAULT_CONFIG = "congestion_heuristics.yaml"
DEFAULT_TEMP_CONFIG = "_tmp_congestion_heuristics_efficient_high.yaml"
DEFAULT_HEURISTICS = ["none", "h1", "h2", "h3"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run all congestion heuristic scenarios with a fixed routing mode "
            "to compare none, h1, h2 and h3."
        )
    )

    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Config filename inside configs/ (default: {DEFAULT_CONFIG})",
    )

    parser.add_argument(
        "--mode-type",
        type=int,
        default=5,
        help=(
            "mode_type to force in every case. "
            "Use 5 for efficient + high awareness if you added that mode."
        ),
    )

    parser.add_argument(
        "--heuristics",
        nargs="+",
        default=DEFAULT_HEURISTICS,
        choices=["none", "h1", "h2", "h3"],
        help="Heuristics to run.",
    )

    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help=(
            "Optional list of case ids to run. "
            "If omitted, all cases in the config are executed."
        ),
    )

    parser.add_argument(
        "--horizon-k",
        type=int,
        default=6,
        help="Horizon k for h2.",
    )

    parser.add_argument(
        "--congestion-reroute-epsilon",
        type=float,
        default=0.15,
        help="Congestion reroute epsilon.",
    )

    parser.add_argument(
        "--runs-dir",
        default="runs/congestion_heuristics_efficient_high",
        help="Base output directory for all runs.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logs.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with the next run if one run fails.",
    )

    parser.add_argument(
        "--keep-temp-config",
        action="store_true",
        help="Keep the temporary generated config inside configs/.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without running simulations.",
    )

    return parser.parse_args()


def load_cases(config_name: str) -> dict[str, dict[str, Any]]:
    config_path = PROJECT_ROOT / "configs" / config_name

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected config to be a mapping: {config_path}")

    return data


def force_mode_type(
    cases: dict[str, dict[str, Any]],
    *,
    mode_type: int,
) -> dict[str, dict[str, Any]]:
    patched_cases = deepcopy(cases)

    for case_id, case_cfg in patched_cases.items():
        if not isinstance(case_cfg, dict):
            raise ValueError(f"Case {case_id!r} must be a mapping")

        case_cfg["mode_type"] = mode_type

    return patched_cases


def write_temp_config(
    patched_cases: dict[str, dict[str, Any]],
    *,
    temp_config_name: str,
) -> Path:
    temp_config_path = PROJECT_ROOT / "configs" / temp_config_name

    temp_config_path.write_text(
        yaml.safe_dump(
            patched_cases,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    return temp_config_path


def selected_case_ids(
    cases: dict[str, dict[str, Any]],
    requested_cases: list[str] | None,
) -> list[str]:
    if not requested_cases:
        return list(cases.keys())

    missing = [
        case_id
        for case_id in requested_cases
        if case_id not in cases
    ]

    if missing:
        raise ValueError(
            "Unknown case id(s): "
            + ", ".join(missing)
        )

    return requested_cases


def build_run_dir(
    *,
    runs_dir: Path,
    heuristic: str,
    case_id: str,
) -> Path:
    safe_case_id = case_id.replace("/", "_").replace("\\", "_")
    return runs_dir / heuristic / safe_case_id


def build_log_file(
    *,
    runs_dir: Path,
    heuristic: str,
    case_id: str,
) -> Path:
    safe_case_id = case_id.replace("/", "_").replace("\\", "_")
    logs_dir = runs_dir / "_logs" / heuristic
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"{safe_case_id}.log"


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


def summarise_evacuation_metrics(out_dir: Path) -> dict[str, Any]:
    """
    Read compact evacuation-time metrics from the run SQLite database.
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

    valid_summaries = [
        summary
        for summary in summaries
        if "error" not in summary
    ]

    if not valid_summaries:
        return {
            "databases": summaries,
        } if summaries else {}

    total_records = sum(int(summary.get("total_records", 0)) for summary in valid_summaries)

    return {
        "groups": sum(int(summary.get("groups", 0)) for summary in valid_summaries),
        "total_records": total_records,
        "avg_time_weighted": _weighted_average(
            [
                (summary.get("avg_time_weighted"), summary.get("total_records", 1))
                for summary in valid_summaries
            ]
        ),
        "median_time_weighted": _weighted_average(
            [
                (summary.get("median_time_weighted"), summary.get("total_records", 1))
                for summary in valid_summaries
            ]
        ),
        "p90_time_weighted": _weighted_average(
            [
                (summary.get("p90_time_weighted"), summary.get("total_records", 1))
                for summary in valid_summaries
            ]
        ),
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


def format_evacuation_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return "evac_avg=- evac_p90=- evac_max=-"

    return (
        "evac_avg={avg} evac_p90={p90} evac_max={max_time}".format(
            avg=_format_seconds(summary.get("avg_time_weighted")),
            p90=_format_seconds(summary.get("p90_time_weighted")),
            max_time=_format_seconds(summary.get("max_time")),
        )
    )


def run_started_line(
    *,
    run_number: int,
    total_runs: int,
    case_id: str,
    heuristic: str,
    mode_type: int,
    out_dir: Path,
) -> str:
    return (
        "[{current}/{total}] RUN  case={case} heuristic={heuristic} "
        "mode_type={mode_type} out={out_dir}".format(
            current=run_number,
            total=total_runs,
            case=case_id,
            heuristic=heuristic,
            mode_type=mode_type,
            out_dir=out_dir,
        )
    )


def run_finished_line(
    *,
    run_number: int,
    total_runs: int,
    case_id: str,
    heuristic: str,
    status: str,
    elapsed_seconds: float,
    evacuation_summary: dict[str, Any],
) -> str:
    return (
        "[{current}/{total}] {status:<4} case={case} heuristic={heuristic} "
        "runtime={runtime:.2f}s {evac}".format(
            current=run_number,
            total=total_runs,
            status=status,
            case=case_id,
            heuristic=heuristic,
            runtime=elapsed_seconds,
            evac=format_evacuation_summary(evacuation_summary),
        )
    )


def run_case(
    *,
    temp_config_name: str,
    case_id: str,
    heuristic: str,
    horizon_k: int,
    congestion_reroute_epsilon: float,
    out_dir: Path,
    log_file: Path,
    verbose: bool,
) -> Path:
    argv = [
        "run",
        "--config",
        temp_config_name,
        "--case",
        case_id,
        "--heuristic",
        heuristic,
        "--horizon-k",
        str(horizon_k),
        "--congestion-reroute-epsilon",
        str(congestion_reroute_epsilon),
        "--out-dir",
        str(out_dir),
    ]

    if verbose:
        argv.append("--verbose")

    with log_file.open("w", encoding="utf-8") as log:
        log.write(f"CLI args: {argv!r}\n\n")
        log.flush()

        with redirect_stdout(log), redirect_stderr(log):
            try:
                result = main(argv)
            except SystemExit as exc:
                result = exc.code

    if result not in (None, 0):
        raise RuntimeError(f"evac_sim.cli returned exit code {result}")

    return log_file


def main_script() -> int:
    args = parse_args()

    started_at = datetime.now().isoformat(timespec="seconds")
    runs_dir = (PROJECT_ROOT / args.runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    cases = load_cases(args.config)

    case_ids = selected_case_ids(
        cases,
        args.cases,
    )

    patched_cases = force_mode_type(
        cases,
        mode_type=args.mode_type,
    )

    temp_config_path = write_temp_config(
        patched_cases,
        temp_config_name=DEFAULT_TEMP_CONFIG,
    )

    manifest: dict[str, Any] = {
        "started_at": started_at,
        "config": args.config,
        "temp_config": str(temp_config_path),
        "forced_mode_type": args.mode_type,
        "horizon_k": args.horizon_k,
        "congestion_reroute_epsilon": args.congestion_reroute_epsilon,
        "heuristics": args.heuristics,
        "cases": case_ids,
        "runs": [],
    }

    manifest_path = runs_dir / "run_manifest.json"

    try:
        total_runs = len(args.heuristics) * len(case_ids)
        run_number = 0

        for heuristic in args.heuristics:
            for case_id in case_ids:
                run_number += 1

                out_dir = build_run_dir(
                    runs_dir=runs_dir,
                    heuristic=heuristic,
                    case_id=case_id,
                )

                log_file = build_log_file(
                    runs_dir=runs_dir,
                    heuristic=heuristic,
                    case_id=case_id,
                )

                print(
                    run_started_line(
                        run_number=run_number,
                        total_runs=total_runs,
                        case_id=case_id,
                        heuristic=heuristic,
                        mode_type=args.mode_type,
                        out_dir=out_dir,
                    ),
                    flush=True,
                )

                run_record = {
                    "case_id": case_id,
                    "heuristic": heuristic,
                    "out_dir": str(out_dir),
                    "log_file": str(log_file),
                    "status": "pending",
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                }

                manifest["runs"].append(run_record)

                if args.dry_run:
                    run_record["status"] = "dry-run"
                    print(
                        run_finished_line(
                            run_number=run_number,
                            total_runs=total_runs,
                            case_id=case_id,
                            heuristic=heuristic,
                            status="DRY",
                            elapsed_seconds=0.0,
                            evacuation_summary={},
                        ),
                        flush=True,
                    )
                    continue

                t0 = time.perf_counter()

                try:
                    log_file = run_case(
                        temp_config_name=DEFAULT_TEMP_CONFIG,
                        case_id=case_id,
                        heuristic=heuristic,
                        horizon_k=args.horizon_k,
                        congestion_reroute_epsilon=args.congestion_reroute_epsilon,
                        out_dir=out_dir,
                        log_file=log_file,
                        verbose=args.verbose,
                    )

                except Exception as exc:
                    elapsed = time.perf_counter() - t0

                    run_record["status"] = "failed"
                    run_record["elapsed_seconds"] = round(elapsed, 3)
                    run_record["error"] = repr(exc)

                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    print(
                        run_finished_line(
                            run_number=run_number,
                            total_runs=total_runs,
                            case_id=case_id,
                            heuristic=heuristic,
                            status="FAIL",
                            elapsed_seconds=elapsed,
                            evacuation_summary={},
                        ),
                        flush=True,
                    )
                    print(f"      reason: {exc!r}", flush=True)

                    if not args.continue_on_error:
                        raise

                else:
                    elapsed = time.perf_counter() - t0

                    evacuation_summary = summarise_evacuation_metrics(out_dir)

                    run_record["status"] = "ok"
                    run_record["elapsed_seconds"] = round(elapsed, 3)
                    run_record["finished_at"] = datetime.now().isoformat(
                        timespec="seconds"
                    )
                    run_record["evacuation_summary"] = evacuation_summary
                    run_record["log_file"] = str(log_file)

                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    print(
                        run_finished_line(
                            run_number=run_number,
                            total_runs=total_runs,
                            case_id=case_id,
                            heuristic=heuristic,
                            status="OK",
                            elapsed_seconds=elapsed,
                            evacuation_summary=evacuation_summary,
                        ),
                        flush=True,
                    )

        manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")

        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print()
        print(f"All requested runs finished. Manifest: {manifest_path}")

        return 0

    finally:
        if not args.keep_temp_config and temp_config_path.exists():
            temp_config_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main_script())