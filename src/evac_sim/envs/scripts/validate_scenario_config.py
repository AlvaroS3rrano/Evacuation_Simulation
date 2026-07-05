"""Validate a scenario configuration before running a simulation.

Checks that sources, targets, agents, risk parameters and connectivity are
coherent.  Writes a normalised YAML if the scenario is valid.

Examples
--------
    python -m evac_sim.envs.scripts.validate_scenario_config \\
        --config configs/management_building.yaml \\
        --scenario basement \\
        --output configs/generated/basement.validated.yaml

    python -m evac_sim.envs.scripts.validate_scenario_config \\
        --config configs/study.yaml \\
        --scenario corridor_case_1
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

ALLOWED_MODE_TYPES = {0, 1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_scenario_config",
        description="Validate a scenario config and (optionally) write a normalised YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file (relative to --project-root or absolute).",
    )
    p.add_argument(
        "--scenario",
        required=True,
        help="Key of the scenario inside the YAML file.",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Where to write the normalised YAML (only written if scenario is VALID).",
    )
    p.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory).",
    )
    return p


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: Path, scenario: str) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw)}")
    if scenario not in raw:
        available = ", ".join(sorted(raw.keys()))
        raise KeyError(
            f"Scenario '{scenario}' not found in {config_path}.\n"
            f"Available scenarios: {available}"
        )
    cfg: dict[str, Any] = dict(raw[scenario])
    return cfg


def _build_graph(edges) -> nx.DiGraph:
    G = nx.DiGraph()
    for source, target, *_ in edges:
        G.add_edge(source, target)
        G.add_edge(target, source)
    return G


def _check_positive_float(value: Any, name: str) -> str | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return f"'{name}' must be a number, got {value!r}."
    if v <= 0:
        return f"'{name}' must be > 0, got {v}."
    return None


def _check_unit_float(value: Any, name: str) -> str | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return f"'{name}' must be a number, got {value!r}."
    if not 0.0 <= v <= 1.0:
        return f"'{name}' must be in [0, 1], got {v}."
    return None


def validate_scenario(cfg: dict[str, Any], scenario: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) lists."""
    from evac_sim.envs.environment_factory import select_environment
    from evac_sim.envs.layout_inspection.current_layout import load_layout_from_environment_data

    errors: list[str] = []
    warnings: list[str] = []

    # --- environment ---
    env_name = cfg.get("environment")
    if not env_name:
        errors.append("'environment' field is missing or empty.")
        return errors, warnings

    try:
        env = select_environment(env_name)
    except ValueError as exc:
        errors.append(str(exc))
        return errors, warnings

    try:
        waypoints, edges, specific_areas = load_layout_from_environment_data(env)
    except Exception as exc:
        errors.append(f"Failed to load layout for '{env_name}': {exc}")
        return errors, warnings

    graph_nodes: set = set(waypoints.keys())
    G = _build_graph(edges)

    # --- sources / agents ---
    sources: list = cfg.get("sources") or []
    agents: list = cfg.get("agents") or []

    if not sources:
        errors.append("'sources' is missing or empty.")
    if not agents:
        errors.append("'agents' is missing or empty.")

    if sources and agents:
        if len(sources) != len(agents):
            errors.append(
                f"'agents' length ({len(agents)}) must equal 'sources' length ({len(sources)})."
            )
        for i, src in enumerate(sources):
            if str(src) not in graph_nodes:
                errors.append(f"source '{src}' does not exist in environment '{env_name}'.")
        for i, n in enumerate(agents):
            try:
                if int(n) <= 0:
                    errors.append(f"agents[{i}] must be > 0, got {n}.")
            except (TypeError, ValueError):
                errors.append(f"agents[{i}] must be an integer, got {n!r}.")

    # --- targets ---
    targets: list = cfg.get("targets") or []
    if not targets:
        errors.append("'targets' is missing or empty.")
    else:
        for tgt in targets:
            if str(tgt) not in graph_nodes:
                errors.append(f"target '{tgt}' does not exist in environment '{env_name}'.")

    # --- connectivity ---
    if sources and targets:
        for src in sources:
            src_str = str(src)
            if src_str not in graph_nodes:
                continue
            reachable = any(
                nx.has_path(G, src_str, str(tgt))
                for tgt in targets
                if str(tgt) in graph_nodes
            )
            if not reachable:
                errors.append(
                    f"target(s) are unreachable from source '{src}' "
                    f"in environment '{env_name}'."
                )

    # --- mode_type ---
    mode_type = cfg.get("mode_type")
    if mode_type is None:
        errors.append("'mode_type' is missing.")
    elif int(mode_type) not in ALLOWED_MODE_TYPES:
        errors.append(
            f"'mode_type' must be one of {sorted(ALLOWED_MODE_TYPES)}, got {mode_type}."
        )

    # --- master_seed ---
    if cfg.get("master_seed") is None:
        new_seed = random.randint(1, 999999)
        cfg["master_seed"] = new_seed
        warnings.append(
            f"'master_seed' was missing; assigned random seed {new_seed}."
        )

    # --- numeric fields ---
    for field in ("gamma", "stairs_max_speed", "normal_max_speed"):
        err = _check_positive_float(cfg.get(field), field)
        if err:
            errors.append(err)

    for field in ("every_nth_frame_simulation", "every_nth_frame_animation", "danger_visualization_frame"):
        val = cfg.get(field)
        if val is not None:
            try:
                if int(val) <= 0:
                    errors.append(f"'{field}' must be > 0, got {val}.")
            except (TypeError, ValueError):
                errors.append(f"'{field}' must be an integer, got {val!r}.")

    # --- risk block ---
    risk = cfg.get("risk") or {}
    if risk.get("enabled"):
        for field in ("risk_iterations", "every_nth_frame_simulation"):
            val = cfg.get(field) if field == "every_nth_frame_simulation" else risk.get(field)
            if val is not None:
                try:
                    if int(val) <= 0:
                        errors.append(f"'risk.{field}' must be > 0, got {val}.")
                except (TypeError, ValueError):
                    errors.append(f"'risk.{field}' must be an integer, got {val!r}.")

        for field in ("risk_increase_chance", "risk_threshold", "propagation_threshold"):
            err = _check_unit_float(risk.get(field), f"risk.{field}")
            if err:
                errors.append(err)

        starting_risks = risk.get("starting_risks") or []
        for entry in starting_risks:
            if not (isinstance(entry, (list, tuple)) and len(entry) == 2):
                errors.append(f"'risk.starting_risks' entry {entry!r} must be [node_id, value].")
                continue
            node_id, risk_val = entry
            if str(node_id) not in graph_nodes:
                errors.append(
                    f"'risk.starting_risks' references unknown node '{node_id}'."
                )
            err = _check_unit_float(risk_val, f"risk.starting_risks[{node_id}]")
            if err:
                errors.append(err)

        risk_overrides = risk.get("risk_overrides") or []
        for entry in risk_overrides:
            if not (isinstance(entry, (list, tuple)) and len(entry) == 3):
                errors.append(
                    f"'risk.risk_overrides' entry {entry!r} must be [frame, node_id, value]."
                )
                continue
            frame, node_id, risk_val = entry
            try:
                if int(frame) < 0:
                    errors.append(f"'risk.risk_overrides' frame must be >= 0, got {frame}.")
            except (TypeError, ValueError):
                errors.append(f"'risk.risk_overrides' frame must be an integer, got {frame!r}.")
            if str(node_id) not in graph_nodes:
                errors.append(
                    f"'risk.risk_overrides' references unknown node '{node_id}'."
                )
            err = _check_unit_float(risk_val, f"risk.risk_overrides[{node_id}]")
            if err:
                errors.append(err)

    # --- narrow passage warnings ---
    for node_id, (position, radius) in waypoints.items():
        if radius < 0.15:
            node_edges = [e for e in edges if str(e[0]) == str(node_id) or str(e[1]) == str(node_id)]
            if len(node_edges) <= 2:
                warnings.append(
                    f"Node '{node_id}' has a very small radius ({radius:.3f} m) "
                    f"and only {len(node_edges)} edge(s) — possible narrow passage."
                )

    return errors, warnings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_validation_report(
    scenario: str,
    errors: list[str],
    warnings: list[str],
    output_path: str | None = None,
) -> None:
    valid = len(errors) == 0
    status = "VALID" if valid else "INVALID"
    print(f"\nScenario: {scenario}")
    print(f"Status:   {status}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    if valid and output_path:
        print(f"\nValidated YAML written to: {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    try:
        cfg = _load_config(config_path, args.scenario)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate_scenario(cfg, args.scenario)

    output_path = None
    if not errors and args.output:
        output_path = args.output
        out = Path(output_path)
        if not out.is_absolute():
            out = project_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            yaml.safe_dump({args.scenario: cfg}, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    print_validation_report(args.scenario, errors, warnings, output_path)

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
