from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_DIR):
    path_as_str = str(path)
    if path_as_str not in sys.path:
        sys.path.insert(0, path_as_str)


from tools.random_experiments.case_generation import (  # noqa: E402
    RandomCaseGenerationSettings,
    build_random_cases,
    load_yaml_mapping,
    write_yaml_mapping,
)
from tools.random_experiments.scenario_space import (  # noqa: E402
    DEFAULT_HEURISTICS,
    SCENARIOS,
)


DEFAULT_BASE_CONFIG = "congestion_heuristics.yaml"
DEFAULT_OUTPUT_CONFIG = "random_efficient_high_congestion.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a standalone YAML config with base and random "
            "efficient-high congestion cases."
        )
    )

    parser.add_argument(
        "--base-config",
        default=DEFAULT_BASE_CONFIG,
        help=(
            "Base config file inside configs/. "
            f"Default: {DEFAULT_BASE_CONFIG}"
        ),
    )

    parser.add_argument(
        "--output-config",
        default=DEFAULT_OUTPUT_CONFIG,
        help=(
            "Output config file inside configs/. "
            f"Default: {DEFAULT_OUTPUT_CONFIG}"
        ),
    )

    parser.add_argument(
        "--configs-per-scenario",
        type=int,
        default=5,
        help=(
            "Total configs per scenario. If --include-base-config is enabled, "
            "this includes the base case. Default: 5."
        ),
    )

    parser.add_argument(
        "--master-seed",
        type=int,
        default=1234,
        help="Master seed for random case generation.",
    )

    parser.add_argument(
        "--agents-per-source-min",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--agents-per-source-max",
        type=int,
        default=80,
    )

    parser.add_argument(
        "--sources-per-case-min",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--sources-per-case-max",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--targets-per-case-min",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--targets-per-case-max",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=list(SCENARIOS.keys()),
        choices=list(SCENARIOS.keys()),
        help="Scenarios to generate.",
    )

    parser.add_argument(
        "--heuristics",
        nargs="+",
        default=DEFAULT_HEURISTICS,
        choices=DEFAULT_HEURISTICS,
        help="Stored only in the metadata JSON. Execution is handled separately.",
    )

    parser.add_argument(
        "--include-base-config",
        action="store_true",
        default=True,
        help="Include the original base case for each scenario.",
    )

    parser.add_argument(
        "--no-base-config",
        action="store_false",
        dest="include_base_config",
        help="Do not include base cases.",
    )

    return parser.parse_args()


def _write_metadata(
    *,
    output_config_path: Path,
    generated_cases: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> Path:
    metadata_path = output_config_path.with_suffix(".metadata.json")

    metadata = {
        "generated_by": "tools/generate_random_congestion_yaml.py",
        "output_config": str(output_config_path),
        "base_config": args.base_config,
        "configs_per_scenario": args.configs_per_scenario,
        "master_seed": args.master_seed,
        "scenarios": args.scenarios,
        "heuristics": args.heuristics,
        "include_base_config": args.include_base_config,
        "agents_per_source_min": args.agents_per_source_min,
        "agents_per_source_max": args.agents_per_source_max,
        "sources_per_case_min": args.sources_per_case_min,
        "sources_per_case_max": args.sources_per_case_max,
        "targets_per_case_min": args.targets_per_case_min,
        "targets_per_case_max": args.targets_per_case_max,
        "generated_cases": list(generated_cases.keys()),
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return metadata_path


def _print_summary(
    *,
    output_path: Path,
    metadata_path: Path,
    generated_cases: dict[str, dict[str, Any]],
) -> None:
    print()
    print("=" * 80)
    print("Generated YAML summary")
    print("=" * 80)
    print(f"Output config: {output_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Generated cases: {len(generated_cases)}")
    print()

    for case_id, case_cfg in generated_cases.items():
        random_info = case_cfg.get("random_experiment", {})
        scenario = random_info.get("scenario", "unknown")

        sources = case_cfg.get("sources", [])
        targets = case_cfg.get("targets", [])
        agents = case_cfg.get("agents", [])
        waypoints = case_cfg.get("waypoints", [])

        print(
            f"- {case_id} | "
            f"scenario={scenario} | "
            f"sources={sources} | "
            f"targets={targets} | "
            f"agents={agents} | "
            f"waypoints={waypoints}"
        )

    print()
    print("Next step:")
    print(
        f"  python .\\tools\\run_all_congestion_heuristics.py "
        f"--config {output_path.name}"
    )
    print()


def main() -> int:
    args = parse_args()

    if args.configs_per_scenario <= 0:
        raise ValueError("--configs-per-scenario must be greater than 0")

    if args.agents_per_source_min <= 0:
        raise ValueError("--agents-per-source-min must be greater than 0")

    if args.agents_per_source_max < args.agents_per_source_min:
        raise ValueError(
            "--agents-per-source-max must be greater than or equal to "
            "--agents-per-source-min"
        )

    base_config_path = PROJECT_ROOT / "configs" / args.base_config
    defaults_path = PROJECT_ROOT / "configs" / "defaults.yaml"
    output_config_path = PROJECT_ROOT / "configs" / args.output_config

    # IMPORTANT:
    # congestion_heuristics.yaml is already a case mapping.
    # It does NOT have a top-level "cases" key.
    base_cases = load_yaml_mapping(base_config_path)
    defaults = load_yaml_mapping(defaults_path) if defaults_path.exists() else {}

    settings = RandomCaseGenerationSettings(
        configs_per_scenario=args.configs_per_scenario,
        master_seed=args.master_seed,
        agents_per_source_min=args.agents_per_source_min,
        agents_per_source_max=args.agents_per_source_max,
        sources_per_case_min=args.sources_per_case_min,
        sources_per_case_max=args.sources_per_case_max,
        targets_per_case_min=args.targets_per_case_min,
        targets_per_case_max=args.targets_per_case_max,
        include_base_config=args.include_base_config,
    )

    generated_cases = build_random_cases(
        base_cases=base_cases,
        defaults=defaults,
        settings=settings,
        scenario_keys=args.scenarios,
    )

    # IMPORTANT:
    # The generated YAML must also be a plain case mapping, just like
    # congestion_heuristics.yaml and _tmp_random_efficient_high_congestion.yaml.
    # Do not wrap it in "cases:".
    write_yaml_mapping(
        output_config_path,
        generated_cases,
    )

    metadata_path = _write_metadata(
        output_config_path=output_config_path,
        generated_cases=generated_cases,
        args=args,
    )

    _print_summary(
        output_path=output_config_path,
        metadata_path=metadata_path,
        generated_cases=generated_cases,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())