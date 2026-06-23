from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import traceback
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
from evac_sim.envs.environment_factory import select_environment


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


def load_case_config(config_path: Path, case_id: str) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if case_id not in config:
        raise KeyError(
            f"Case {case_id!r} not found in {config_path}. "
            f"Available cases: {list(config)}"
        )

    case_cfg = config[case_id]

    if not isinstance(case_cfg, dict):
        raise ValueError(f"Case {case_id!r} is not a mapping.")

    return case_cfg


def preflight_case(case_cfg: dict[str, Any]) -> None:
    env = select_environment(case_cfg["environment"])

    sources = [str(node) for node in case_cfg.get("sources", [])]
    targets = [str(node) for node in case_cfg.get("targets", [])]
    agents = case_cfg.get("agents", [])

    graph_nodes = {str(node) for node in env.graph.nodes}
    area_nodes = {str(node) for node in env.specific_areas}
    waypoint_nodes = {str(node) for node in env.waypoints}

    print()
    print("=" * 80)
    print("PREFLIGHT")
    print("=" * 80)
    print(f"environment: {env.name}")
    print(f"sources: {sources}")
    print(f"targets: {targets}")
    print(f"agents: {agents}")
    print(f"graph nodes: {len(graph_nodes)}")
    print(f"specific areas: {len(area_nodes)}")
    print(f"waypoints: {len(waypoint_nodes)}")

    missing_source_areas = [source for source in sources if source not in area_nodes]
    missing_source_graph = [source for source in sources if source not in graph_nodes]
    missing_target_areas = [target for target in targets if target not in area_nodes]
    missing_target_graph = [target for target in targets if target not in graph_nodes]

    if missing_source_areas:
        print(f"WARNING missing source specific_areas: {missing_source_areas}")

    if missing_source_graph:
        print(f"WARNING missing source graph nodes: {missing_source_graph}")

    if missing_target_areas:
        print(f"WARNING missing target specific_areas: {missing_target_areas}")

    if missing_target_graph:
        print(f"WARNING missing target graph nodes: {missing_target_graph}")

    if len(sources) != len(agents):
        print(
            "WARNING sources/agents length mismatch: "
            f"{len(sources)} sources vs {len(agents)} agent counts"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run and profile a single congestion simulation case. Useful to "
            "check whether a simulation works and where it fails."
        )
    )

    parser.add_argument("--config", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument(
        "--heuristic",
        default="h3",
        choices=["none", "h1", "h2", "h3"],
    )
    parser.add_argument("--horizon-k", type=int, default=6)
    parser.add_argument("--congestion-reroute-epsilon", type=float, default=0.15)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output dir. Default: runs/profile_single/<heuristic>/<case>",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Generate cProfile stats.",
    )

    return parser.parse_args()


def run_simulation(args: argparse.Namespace, out_dir: Path) -> int:
    argv = [
        "run",
        "--config",
        args.config,
        "--case",
        args.case,
        "--heuristic",
        args.heuristic,
        "--horizon-k",
        str(args.horizon_k),
        "--congestion-reroute-epsilon",
        str(args.congestion_reroute_epsilon),
        "--out-dir",
        str(out_dir),
    ]

    print()
    print("=" * 80)
    print("RUN")
    print("=" * 80)
    print(f"CLI args: {argv}")

    return int(evac_sim_main(argv) or 0)


def main() -> int:
    args = parse_args()

    config_path = resolve_config_path(args.config)
    case_cfg = load_case_config(config_path, args.case)

    preflight_case(case_cfg)

    out_dir = (
        (PROJECT_ROOT / "runs" / "profile_single" / args.heuristic / args.case)
        if args.out_dir is None
        else args.out_dir
    ).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.profile:
            profiler = cProfile.Profile()
            profiler.enable()

            status = run_simulation(args, out_dir)

            profiler.disable()

            stats_buffer = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_buffer)
            stats.sort_stats("cumtime")
            stats.print_stats(80)

            profile_path = out_dir / "profile_cumtime.txt"
            profile_path.write_text(stats_buffer.getvalue(), encoding="utf-8")

            print()
            print(f"Profile written to: {profile_path}")
        else:
            status = run_simulation(args, out_dir)

        print()
        print("=" * 80)
        print("SUCCESS" if status == 0 else "FINISHED WITH NON-ZERO STATUS")
        print("=" * 80)
        print(f"Output dir: {out_dir}")

        return status

    except Exception:
        error_path = out_dir / "error_traceback.txt"
        error_text = traceback.format_exc()
        error_path.write_text(error_text, encoding="utf-8")

        print()
        print("=" * 80)
        print("FAILED")
        print("=" * 80)
        print(error_text)
        print(f"Traceback written to: {error_path}")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
