from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_DIR):
    path_as_str = str(path)
    if path_as_str not in sys.path:
        sys.path.insert(0, path_as_str)

from evac_sim.cli import main as evac_sim_main


DEFAULT_HEURISTICS = ["none", "h1", "h2", "h3"]


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")

    return data


def write_yaml_mapping(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def resolve_config_path(config_name_or_path: str) -> Path:
    raw_path = Path(config_name_or_path)

    if raw_path.exists():
        return raw_path.resolve()

    config_path = PROJECT_ROOT / "configs" / config_name_or_path

    if config_path.exists():
        return config_path.resolve()

    raise FileNotFoundError(
        f"Config file not found as path or inside configs/: {config_name_or_path}"
    )


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def read_run_metrics(run_dir: Path) -> dict[str, Any]:
    metric_candidates = [
        run_dir / "artifacts" / "csv" / "comparison_metrics.csv",
        run_dir / "artifacts" / "csv" / "experiment_metrics.csv",
    ]

    for csv_path in metric_candidates:
        if not csv_path.exists() or csv_path.stat().st_size == 0:
            continue

        try:
            import pandas as pd
            df = pd.read_csv(csv_path)
        except Exception:
            continue

        if df.empty:
            continue

        result: dict[str, Any] = {}

        for metric in [
            "avg_evac_time",
            "p90_evac_time",
            "max_evac_time",
            "avg_density_exposure",
            "high_density_agent_ratio",
        ]:
            for column in [f"{metric}_weighted", metric]:
                if column in df.columns:
                    result[metric] = float(df[column].mean())
                    break

        return result

    return {}


def run_case(
    *,
    temp_config_name: str,
    case_id: str,
    heuristic: str,
    horizon_k: int,
    congestion_reroute_epsilon: float,
    out_dir: Path,
    continue_on_error: bool,
) -> dict[str, Any]:
    runs_dir = out_dir.parents[1]
    log_dir = runs_dir / "_runner_logs" / heuristic
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{case_id}.log"

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

    start = time.perf_counter()

    try:
        with log_file.open("w", encoding="utf-8") as handle:
            handle.write(f"CLI args: {argv!r}\n\n")
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            try:
                sys.stdout = handle
                sys.stderr = handle
                result = evac_sim_main(argv)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        runtime = time.perf_counter() - start

        if result not in (0, None):
            raise RuntimeError(f"evac_sim returned non-zero status: {result}")

        metrics = read_run_metrics(out_dir)

        return {
            "status": "ok",
            "runtime_seconds": runtime,
            "log_file": str(log_file),
            **metrics,
        }

    except Exception as exc:
        runtime = time.perf_counter() - start

        with log_file.open("a", encoding="utf-8") as handle:
            handle.write("\n")
            handle.write("ERROR\n")
            handle.write("=" * 80)
            handle.write("\n")
            handle.write(traceback.format_exc())

        if not continue_on_error:
            raise

        return {
            "status": "failed",
            "runtime_seconds": runtime,
            "log_file": str(log_file),
            "error": repr(exc),
        }


def build_temp_config(
    *,
    input_config_path: Path,
    temp_config_path: Path,
    cases: list[str] | None,
    mode_type: int,
) -> dict[str, dict[str, Any]]:
    config = load_yaml_mapping(input_config_path)

    selected_cases: dict[str, dict[str, Any]] = {}

    for case_id, case_cfg in config.items():
        if cases and case_id not in set(cases):
            continue

        if not isinstance(case_cfg, dict):
            continue

        updated_case = dict(case_cfg)
        updated_case["mode_type"] = mode_type
        selected_cases[case_id] = updated_case

    if not selected_cases:
        raise RuntimeError("No cases selected for execution.")

    write_yaml_mapping(temp_config_path, selected_cases)

    return selected_cases


def run_command(command: list[str], *, cwd: Path) -> None:
    print()
    print("=" * 80)
    print("RUNNING POST-PROCESS")
    print("=" * 80)
    print(" ".join(str(part) for part in command))
    print()

    subprocess.run(
        command,
        cwd=str(cwd),
        check=True,
    )


def run_reports(
    *,
    runs_dir: Path,
    config_name: str,
    heuristics: list[str],
    baseline: str,
    with_visual_pdfs: bool,
    skip_scenario_report: bool,
) -> None:
    compare_script = PROJECT_ROOT / "tools" / "compare_congestion_heuristics.py"

    compare_command = [
        sys.executable,
        str(compare_script),
        "--runs-dir",
        str(runs_dir),
        "--baseline",
        baseline,
        "--heuristics",
        *heuristics,
        "--simulation-config",
        config_name,
    ]

    if not with_visual_pdfs:
        compare_command.append("--skip-visual-pdfs")

    run_command(
        compare_command,
        cwd=PROJECT_ROOT,
    )

    if not skip_scenario_report:
        scenario_script = PROJECT_ROOT / "tools" / "compare_congestion_by_scenario.py"

        scenario_command = [
            sys.executable,
            str(scenario_script),
            "--run-root",
            str(runs_dir),
            "--baseline",
            baseline,
        ]

        run_command(
            scenario_command,
            cwd=PROJECT_ROOT,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run all cases from a YAML config with congestion heuristics "
            "none, h1, h2 and h3."
        )
    )

    parser.add_argument(
        "--config",
        default="congestion_heuristics.yaml",
        help="YAML config filename inside configs/ or explicit path.",
    )

    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs/congestion_heuristics_efficient_high"),
        help="Output root for all runs.",
    )

    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional case ids to run. By default all cases are executed.",
    )

    parser.add_argument(
        "--heuristics",
        nargs="+",
        default=DEFAULT_HEURISTICS,
        choices=DEFAULT_HEURISTICS,
        help="Heuristics to execute.",
    )

    parser.add_argument(
        "--mode-type",
        type=int,
        default=5,
        help="Mode type forced for all selected cases. Default: 5.",
    )

    parser.add_argument(
        "--horizon-k",
        type=int,
        default=6,
        help="Reservation horizon k used by congestion heuristics.",
    )

    parser.add_argument(
        "--congestion-reroute-epsilon",
        type=float,
        default=0.15,
        help="Congestion reroute epsilon.",
    )

    parser.add_argument(
        "--baseline",
        default="none",
        choices=DEFAULT_HEURISTICS,
        help="Baseline heuristic used by comparison reports.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with the next run if one simulation fails.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create temporary config and manifest but do not execute simulations.",
    )

    parser.add_argument(
        "--skip-comparison",
        action="store_true",
        help="Do not generate comparison reports after finishing simulations.",
    )

    parser.add_argument(
        "--skip-scenario-report",
        action="store_true",
        help="Do not generate the scenario-level comparison report.",
    )

    parser.add_argument(
        "--with-visual-pdfs",
        action="store_true",
        help=(
            "Generate trajectory and congestion visual comparison PDFs. "
            "Disabled by default because it can be slow."
        ),
    )

    return parser.parse_args()


def main_script() -> int:
    args = parse_args()

    config_path = resolve_config_path(args.config)
    runs_dir = (PROJECT_ROOT / args.runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    temp_config_name = "_tmp_congestion_heuristics_efficient_high.yaml"
    temp_config_path = PROJECT_ROOT / "configs" / temp_config_name

    selected_cases = build_temp_config(
        input_config_path=config_path,
        temp_config_path=temp_config_path,
        cases=args.cases,
        mode_type=args.mode_type,
    )

    run_plan = [
        (heuristic, case_id)
        for heuristic in args.heuristics
        for case_id in selected_cases
    ]

    manifest = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "config": str(config_path),
        "temp_config": str(temp_config_path),
        "runs_dir": str(runs_dir),
        "mode_type": args.mode_type,
        "horizon_k": args.horizon_k,
        "congestion_reroute_epsilon": args.congestion_reroute_epsilon,
        "heuristics": args.heuristics,
        "cases": list(selected_cases),
        "runs": [],
    }

    manifest_path = runs_dir / "run_manifest.json"

    if args.dry_run:
        manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Dry run finished. Manifest: {manifest_path}")
        print(f"Temporary config: {temp_config_path}")
        return 0

    total = len(run_plan)
    global_start = time.perf_counter()

    for index, (heuristic, case_id) in enumerate(run_plan, start=1):
        out_dir = runs_dir / heuristic / case_id

        print(
            f"[{index}/{total}] RUN  case={case_id} heuristic={heuristic} "
            f"mode_type={args.mode_type} out={out_dir}"
        )

        result = run_case(
            temp_config_name=temp_config_name,
            case_id=case_id,
            heuristic=heuristic,
            horizon_k=args.horizon_k,
            congestion_reroute_epsilon=args.congestion_reroute_epsilon,
            out_dir=out_dir,
            continue_on_error=args.continue_on_error,
        )

        result_row = {
            "case_id": case_id,
            "heuristic": heuristic,
            "out_dir": str(out_dir),
            **result,
        }

        manifest["runs"].append(result_row)

        runtime = result.get("runtime_seconds", 0.0)

        if result["status"] == "ok":
            print(
                f"[{index}/{total}] OK   case={case_id} heuristic={heuristic} "
                f"runtime={runtime:.2f}s "
                f"evac_avg={result.get('avg_evac_time', '-')} "
                f"evac_p90={result.get('p90_evac_time', '-')} "
                f"evac_max={result.get('max_evac_time', '-')}"
            )
        else:
            print(
                f"[{index}/{total}] FAIL case={case_id} heuristic={heuristic} "
                f"runtime={runtime:.2f}s"
            )
            print(f"      reason: {result.get('error')}")
            print(f"      log: {result.get('log_file')}")

        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["total_runtime"] = format_duration(time.perf_counter() - global_start)

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("All requested runs finished.")
    print(f"Manifest: {manifest_path}")
    print(f"Total runtime: {manifest['total_runtime']}")

    if not args.skip_comparison:
        run_reports(
            runs_dir=runs_dir,
            config_name=args.config,
            heuristics=args.heuristics,
            baseline=args.baseline,
            with_visual_pdfs=args.with_visual_pdfs,
            skip_scenario_report=args.skip_scenario_report,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main_script())
