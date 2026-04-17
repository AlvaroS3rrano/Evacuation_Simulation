import argparse
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
        "--environment",
        default=None,
        help="Run all cases whose environment matches this value"
    )
    run.add_argument("--project-root", default=".", help="Project root (default: current dir)")
    run.add_argument(
        "--out-dir", default=None, help="Output directory (default: ./runs/<timestamp>_<case>)"
    )
    run.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")
    run.add_argument("--heuristic",
                     choices=["none" ,"h1", "h2", "h3"],
                     default=None,
                     help="Routing heuristic to use (default: none)"
    )
    run.add_argument(
        "--beta",
        type=float,
        default=1.0,
        help="Beta parameter for routing heuristics (default: 1.0)",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        if args.case is not None and args.environment is not None:
            parser.error("Use either --case or --environment, not both.")

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
            beta=args.beta,
        )
        return 0

    return 2
