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
        default="representative_case",
        help="Case id inside the YAML (default: representative_case)",
    )
    run.add_argument("--project-root", default=".", help="Project root (default: current dir)")
    run.add_argument(
        "--out-dir", default=None, help="Output directory (default: ./runs/<timestamp>_<case>)"
    )
    run.add_argument("-v", "--verbose", action="store_true", help="Verbose logs")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "run":
        project_root = Path(args.project_root).resolve()
        run_from_yaml(
            project_root=project_root,
            config_name=args.config,
            case_id=args.case,
            out_dir=Path(args.out_dir).resolve() if args.out_dir else None,
            verbose=getattr(args, "verbose", False),
        )
        return 0

    return 2
