from __future__ import annotations

import argparse
import json
import random
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

for path in (PROJECT_ROOT, SRC_DIR):
    path_as_str = str(path)
    if path_as_str not in sys.path:
        sys.path.insert(0, path_as_str)

from tools.random_experiments.case_generation import (
    RandomCaseGenerationSettings,
    build_random_cases,
    load_yaml_mapping,
    write_yaml_mapping,
)
from tools.random_experiments.scenario_space import (
    DEFAULT_HEURISTICS,
    SCENARIOS,
)


DEFAULT_BASE_CONFIG = "congestion_heuristics.yaml"
DEFAULT_OUTPUT_CONFIG = "random_efficient_high_congestion.yaml"


def parse_required_nodes(values: list[str] | None) -> dict[str, list[str]]:
    """
    Parses arguments like:
        short_vs_wide:34,33
        two_exits:17,63

    Returns:
        {"short_vs_wide": ["34", "33"], "two_exits": ["17", "63"]}
    """
    required: dict[str, list[str]] = {}

    for raw_value in values or []:
        if ":" not in raw_value:
            raise ValueError(
                "Required nodes must use '<scenario>:<node1>,<node2>' format. "
                f"Invalid value: {raw_value!r}"
            )

        scenario_key, nodes_raw = raw_value.split(":", 1)
        scenario_key = scenario_key.strip()

        if scenario_key not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {scenario_key!r}. "
                f"Available scenarios: {', '.join(SCENARIOS)}"
            )

        nodes = [
            node.strip()
            for node in re.split(r"[,\\s]+", nodes_raw)
            if node.strip()
        ]

        required.setdefault(scenario_key, [])

        for node in nodes:
            if node not in required[scenario_key]:
                required[scenario_key].append(node)

    return required


def _validate_required_nodes(
    *,
    required_sources: dict[str, list[str]],
    required_targets: dict[str, list[str]],
) -> None:
    for scenario_key, sources in required_sources.items():
        available = {str(node) for node in SCENARIOS[scenario_key].possible_sources}
        invalid = sorted(set(sources) - available)

        if invalid:
            raise ValueError(
                f"Invalid required source(s) for scenario {scenario_key!r}: "
                f"{invalid}. Available: {sorted(available)}"
            )

    for scenario_key, targets in required_targets.items():
        available = {str(node) for node in SCENARIOS[scenario_key].possible_targets}
        invalid = sorted(set(targets) - available)

        if invalid:
            raise ValueError(
                f"Invalid required target(s) for scenario {scenario_key!r}: "
                f"{invalid}. Available: {sorted(available)}"
            )


def _ensure_required_nodes_in_generated_cases(
    *,
    generated_cases: dict[str, dict[str, Any]],
    required_sources: dict[str, list[str]],
    required_targets: dict[str, list[str]],
    agents_per_source_min: int,
    agents_per_source_max: int,
    master_seed: int,
) -> None:
    """
    Post-processes generated random cases so that selected required sources and
    targets are always present. Base cases are intentionally preserved as-is.
    """
    rng = random.Random(master_seed + 911)

    for case_id, case_cfg in generated_cases.items():
        random_info = case_cfg.get("random_experiment", {})
        scenario_key = random_info.get("scenario")

        if not scenario_key or scenario_key not in SCENARIOS:
            continue

        if random_info.get("is_base_config"):
            continue

        scenario = SCENARIOS[scenario_key]

        sources = [str(node) for node in case_cfg.get("sources", [])]
        targets = [str(node) for node in case_cfg.get("targets", [])]
        agents = [int(value) for value in case_cfg.get("agents", [])]

        for required_source in required_sources.get(scenario_key, []):
            required_source = str(required_source)

            if required_source not in sources:
                sources.append(required_source)
                agents.append(
                    rng.randint(
                        agents_per_source_min,
                        agents_per_source_max,
                    )
                )

        for required_target in required_targets.get(scenario_key, []):
            required_target = str(required_target)

            if required_target not in targets:
                targets.append(required_target)

        selected_targets = set(targets)
        existing_waypoints = [str(node) for node in case_cfg.get("waypoints", [])]

        non_selected_targets = [
            str(node)
            for node in scenario.possible_targets
            if str(node) not in selected_targets
        ]

        case_cfg["sources"] = sources
        case_cfg["targets"] = targets
        case_cfg["agents"] = agents
        case_cfg["waypoints"] = list(
            dict.fromkeys(
                [
                    *existing_waypoints,
                    *non_selected_targets,
                ]
            )
        )

        case_cfg.setdefault("random_experiment", {})
        case_cfg["random_experiment"]["required_sources"] = required_sources.get(
            scenario_key,
            [],
        )
        case_cfg["random_experiment"]["required_targets"] = required_targets.get(
            scenario_key,
            [],
        )
        case_cfg["random_experiment"]["final_sources"] = sources
        case_cfg["random_experiment"]["final_targets"] = targets
        case_cfg["random_experiment"]["final_agents"] = agents


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
        help=f"Base config file inside configs/. Default: {DEFAULT_BASE_CONFIG}",
    )

    parser.add_argument(
        "--output-config",
        default=DEFAULT_OUTPUT_CONFIG,
        help=f"Output config file inside configs/. Default: {DEFAULT_OUTPUT_CONFIG}",
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

    parser.add_argument("--agents-per-source-min", type=int, default=20)
    parser.add_argument("--agents-per-source-max", type=int, default=80)

    parser.add_argument("--sources-per-case-min", type=int, default=1)
    parser.add_argument("--sources-per-case-max", type=int, default=4)

    parser.add_argument("--targets-per-case-min", type=int, default=1)
    parser.add_argument("--targets-per-case-max", type=int, default=3)

    parser.add_argument(
        "--required-sources",
        nargs="*",
        default=[],
        help=(
            "Nodes that must always appear as sources in generated random cases. "
            "Format: scenario:node1,node2. Example: short_vs_wide:34,33"
        ),
    )

    parser.add_argument(
        "--required-targets",
        nargs="*",
        default=[],
        help=(
            "Nodes that must always appear as targets in generated random cases. "
            "Format: scenario:node1,node2. Example: two_exits:17,63"
        ),
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
    required_sources: dict[str, list[str]],
    required_targets: dict[str, list[str]],
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
        "required_sources": required_sources,
        "required_targets": required_targets,
        "agents_per_source_min": args.agents_per_source_min,
        "agents_per_source_max": args.agents_per_source_max,
        "sources_per_case_min": args.sources_per_case_min,
        "sources_per_case_max": args.sources_per_case_max,
        "targets_per_case_min": args.targets_per_case_min,
        "targets_per_case_max": args.targets_per_case_max,
        "generated_cases": list(generated_cases.keys()),
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
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
            f"- {case_id} | scenario={scenario} | "
            f"sources={sources} | targets={targets} | "
            f"agents={agents} | waypoints={waypoints}"
        )

    print()
    print("Next step:")
    print(
        "  python .\\tools\\run_all_congestion_heuristics.py "
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

    required_sources = parse_required_nodes(args.required_sources)
    required_targets = parse_required_nodes(args.required_targets)

    _validate_required_nodes(
        required_sources=required_sources,
        required_targets=required_targets,
    )

    base_config_path = PROJECT_ROOT / "configs" / args.base_config
    defaults_path = PROJECT_ROOT / "configs" / "defaults.yaml"
    output_config_path = PROJECT_ROOT / "configs" / args.output_config

    # congestion_heuristics.yaml is a case mapping, not a top-level `cases` object.
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

    _ensure_required_nodes_in_generated_cases(
        generated_cases=generated_cases,
        required_sources=required_sources,
        required_targets=required_targets,
        agents_per_source_min=args.agents_per_source_min,
        agents_per_source_max=args.agents_per_source_max,
        master_seed=args.master_seed,
    )

    write_yaml_mapping(output_config_path, generated_cases)

    metadata_path = _write_metadata(
        output_config_path=output_config_path,
        generated_cases=generated_cases,
        args=args,
        required_sources=required_sources,
        required_targets=required_targets,
    )

    _print_summary(
        output_path=output_config_path,
        metadata_path=metadata_path,
        generated_cases=generated_cases,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
