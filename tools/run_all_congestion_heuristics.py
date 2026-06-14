from __future__ import annotations

import argparse
import json
import sys
import time
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
        "--beta",
        type=float,
        default=1.0,
        help="Beta parameter for congestion heuristics.",
    )

    parser.add_argument(
        "--horizon-k",
        type=int,
        default=3,
        help="Horizon k for h2.",
    )

    parser.add_argument(
        "--congestion-reroute-epsilon",
        type=float,
        default=0.1,
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


def run_case(
    *,
    temp_config_name: str,
    case_id: str,
    heuristic: str,
    beta: float,
    horizon_k: int,
    congestion_reroute_epsilon: float,
    out_dir: Path,
    verbose: bool,
) -> None:
    argv = [
        "run",
        "--config",
        temp_config_name,
        "--case",
        case_id,
        "--heuristic",
        heuristic,
        "--beta",
        str(beta),
        "--horizon-k",
        str(horizon_k),
        "--congestion-reroute-epsilon",
        str(congestion_reroute_epsilon),
        "--out-dir",
        str(out_dir),
    ]

    if verbose:
        argv.append("--verbose")

    main(argv)


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
        "beta": args.beta,
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

                print(
                    f"[{run_number}/{total_runs}] "
                    f"case={case_id} heuristic={heuristic} "
                    f"mode_type={args.mode_type}"
                )
                print(f"  -> {out_dir}")

                run_record = {
                    "case_id": case_id,
                    "heuristic": heuristic,
                    "out_dir": str(out_dir),
                    "status": "pending",
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                }

                manifest["runs"].append(run_record)

                if args.dry_run:
                    run_record["status"] = "dry-run"
                    continue

                t0 = time.perf_counter()

                try:
                    run_case(
                        temp_config_name=DEFAULT_TEMP_CONFIG,
                        case_id=case_id,
                        heuristic=heuristic,
                        beta=args.beta,
                        horizon_k=args.horizon_k,
                        congestion_reroute_epsilon=args.congestion_reroute_epsilon,
                        out_dir=out_dir,
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

                    print(f"  !! FAILED: {exc!r}")

                    if not args.continue_on_error:
                        raise

                else:
                    elapsed = time.perf_counter() - t0

                    run_record["status"] = "ok"
                    run_record["elapsed_seconds"] = round(elapsed, 3)
                    run_record["finished_at"] = datetime.now().isoformat(
                        timespec="seconds"
                    )

                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    print(f"  OK in {elapsed:.1f}s")

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