from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evac_sim.metrics.config import load_metrics_config, metrics_override_from_case  # noqa: E402
from evac_sim.metrics.derived_metrics import build_derived_metrics_for_db  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build derived evacuation, route and density metrics from simulation databases."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=PROJECT_ROOT / "runs" / "congestion_heuristics_efficient_high",
        help="Base run directory containing simulation.db files.",
    )
    parser.add_argument(
        "--metrics-config",
        type=Path,
        default=PROJECT_ROOT / "configs" / "metrics" / "default_metrics.yaml",
        help="Default metrics YAML configuration.",
    )
    parser.add_argument(
        "--simulation-config",
        type=Path,
        default=None,
        help="Optional simulation YAML config. Used to read per-case metrics overrides.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Optional case id filter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show databases that would be processed without writing CSV files.",
    )
    return parser.parse_args()


def load_simulation_cases(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}

    if not path.is_absolute():
        path = PROJECT_ROOT / "configs" / path

    if not path.exists():
        raise FileNotFoundError(f"Simulation config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Simulation config must be a mapping: {path}")

    return data


def infer_case_id_from_db(db_path: Path) -> str:
    # Expected layout:
    # runs_dir / heuristic / case_id / artifacts / db / simulation.db
    try:
        return db_path.parents[2].name
    except IndexError:
        return db_path.parent.name


def main() -> int:
    args = parse_args()
    runs_dir = args.runs_dir.resolve()
    selected_cases = set(args.case or [])
    simulation_cases = load_simulation_cases(args.simulation_config)

    db_paths = sorted(runs_dir.rglob("simulation.db"))

    if selected_cases:
        db_paths = [path for path in db_paths if infer_case_id_from_db(path) in selected_cases]

    if not db_paths:
        raise RuntimeError(f"No simulation.db files found under {runs_dir}")

    manifest: list[dict[str, Any]] = []

    for index, db_path in enumerate(db_paths, start=1):
        case_id = infer_case_id_from_db(db_path)
        case_cfg = simulation_cases.get(case_id, {})
        metrics_config = load_metrics_config(
            config_path=args.metrics_config,
            case_override=metrics_override_from_case(case_cfg),
        )

        print(f"[{index}/{len(db_paths)}] metrics case={case_id} db={db_path}", flush=True)

        if args.dry_run:
            manifest.append({"case_id": case_id, "db_path": str(db_path), "status": "dry-run"})
            continue

        paths = build_derived_metrics_for_db(
            db_path,
            metrics_config=metrics_config,
        )

        manifest.append(
            {
                "case_id": case_id,
                "db_path": str(db_path),
                "status": "ok",
                "density_metrics": str(paths.density_metrics),
                "evacuation_metrics": str(paths.evacuation_metrics),
                "comparison_metrics": str(paths.comparison_metrics),
            }
        )

    manifest_path = runs_dir / "derived_metrics_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"Derived metrics finished. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
