import argparse
import sys
from pathlib import Path

from evac_sim.runner import run_from_yaml


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evac-sim")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run an experiment case from a YAML config")
    run.add_argument(
        "--config",
        default="study.yaml",
        help="Config filename inside ./configs (default: study.yaml)",
    )
    run.add_argument(
        "--case",
        default=None,
        help="Case id inside the YAML",
    )
    run.add_argument(
        "--scenario",
        default=None,
        help="Alias of --case. When given (alone or with --output-format), also "
        "writes result.json/CSV/HTML like run_scenario (see --output-format).",
    )
    run.add_argument(
        "--environment",
        default=None,
        help="Run all cases whose environment matches this value"
    )
    run.add_argument("--project-root", default=".", help="Project root (default: current dir)")
    run.add_argument(
        "--out-dir", default=None, help="Output directory (default: ./runs/<timestamp>_<case>)"
    )
    run.add_argument(
        "--output-dir",
        default=None,
        help="Alias of --out-dir.",
    )
    run.add_argument(
        "--output-format",
        default=None,
        help=(
            "Comma-separated output formats to write: json, csv, html "
            "(default when used: json,csv). Requires --scenario/--case (a single "
            "case, not --environment). Enables the same JSON/CSV/HTML export as "
            "run_scenario."
        ),
    )
    run.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    run.add_argument("--heuristic",
                     choices=["none" ,"h1", "h2", "h3"],
                     default="none",
                     help="Routing heuristic to use (default: none)"
    )
    run.add_argument(
        "--horizon-k",
        type=int,
        default=6,
        help="Number of future edges reserved by heuristic h2 (default: 3)",
    )
    run.add_argument(
        "--congestion-reroute-epsilon",
        type=float,
        default=0.1,
        help="Route improvement percentage to reroute because of congestion (default: 0.1)",
    )

    validate = sub.add_parser(
        "validate", help="Validate a scenario config (wraps validate_scenario_config)"
    )
    validate.add_argument(
        "--config",
        required=True,
        help="Path to the YAML config file (relative to --project-root or absolute).",
    )
    validate.add_argument(
        "--scenario",
        required=True,
        help="Key of the scenario inside the YAML file.",
    )
    validate.add_argument(
        "--output",
        default=None,
        help="Where to write the normalised YAML (only written if scenario is VALID).",
    )
    validate.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory).",
    )

    # No arguments declared here: "inspect" forwards its args as-is to
    # inspect_grid_layout (see main() below), which is intercepted before
    # argparse parsing. argparse.REMAINDER is unreliable for a positional
    # whose first forwarded token starts with "-" right after a subcommand
    # name, so we deliberately don't rely on it.
    sub.add_parser(
        "inspect",
        help=(
            "Inspect a grid layout (wraps inspect_grid_layout; see "
            "'python -m evac_sim.envs.scripts.inspect_grid_layout --help' for its flags)"
        ),
    )

    return p


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "inspect":
        from evac_sim.envs.scripts import inspect_grid_layout

        return inspect_grid_layout.main(argv[1:]) or 0

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        if args.case is not None and args.environment is not None:
            parser.error("Use either --case or --environment, not both.")
        if args.scenario is not None and args.environment is not None:
            parser.error("Use either --scenario or --environment, not both.")

        wants_export = args.scenario is not None or args.output_format is not None

        if wants_export:
            if args.environment is not None:
                parser.error("--output-format/--scenario require a single case, not --environment.")

            scenario = args.scenario if args.scenario is not None else args.case
            if scenario is None:
                parser.error("--output-format requires --scenario (or --case).")

            output_dir = args.output_dir if args.output_dir is not None else args.out_dir

            from evac_sim.simulation.scripts.run_scenario import run_and_postprocess

            return run_and_postprocess(
                config=args.config,
                scenario=scenario,
                output_dir=output_dir,
                output_format=args.output_format or "json,csv",
                project_root=args.project_root,
                heuristic=args.heuristic,
                horizon_k=args.horizon_k,
                congestion_reroute_epsilon=args.congestion_reroute_epsilon,
                verbose=getattr(args, "verbose", False),
            )

        project_root = Path(args.project_root).resolve()

        out_dir = None
        if args.out_dir is not None:
            out_dir = Path(args.out_dir).resolve()

        run_from_yaml(
            project_root=project_root,
            config_name=args.config,
            case_id=args.case,
            environment=args.environment,
            out_dir=out_dir,
            verbose=getattr(args, "verbose", False),
            heuristic=args.heuristic,
            horizon_k=args.horizon_k,
            congestion_reroute_epsilon=args.congestion_reroute_epsilon,
        )
        return 0

    if args.cmd == "validate":
        from evac_sim.envs.scripts.validate_scenario_config import validate_and_report

        return validate_and_report(
            config=args.config,
            scenario=args.scenario,
            output=args.output,
            project_root=args.project_root,
        )

    if args.cmd == "inspect":
        from evac_sim.envs.scripts import inspect_grid_layout

        return inspect_grid_layout.main(args.inspect_args) or 0

    return 2
