from __future__ import annotations

import datetime as dt
import json
import logging
import platform
import sys

from pathlib import Path
from typing import Optional

import yaml

from evac_sim.io.run_paths import prepare_paths, git_commit_hash, prepare_batch_paths, prepare_case_paths
from evac_sim.io.config_loader import deep_merge, select_cases
from evac_sim.io.logging_setup import setup_run_logging
from evac_sim.orchestration.experiment_runner import run_experiment_from_case
from evac_sim.db.sqlite_utils import init_db_connection
from evac_sim.db.simulation_results_db_manager import (
    create_tables,
    export_experiment_metrics_to_csv,
    export_experiments_to_csv,
)

log = logging.getLogger(__name__)


def run_from_yaml(
    *,
    project_root: Path,
    config_name: str,
    case_id: str | None = None,
    environment: str | None = None,
    out_dir: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    project_root = project_root.resolve()

    config_file = project_root / "configs" / config_name
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    defaults_file = project_root / "configs" / "defaults.yaml"
    defaults = {}
    if defaults_file.exists():
        defaults = yaml.safe_load(defaults_file.read_text(encoding="utf-8")) or {}

    study_data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    cases = study_data

    if not isinstance(cases, dict):
        raise ValueError(f"Expected cases to be a mapping in {config_file}")

    selected_cases = select_cases(
        cases=cases,
        case_id=case_id,
        environment=environment,
    )

    if not selected_cases:
        raise ValueError(
            f"No cases matched the provided filters "
            f"(case_id={case_id!r}, environment={environment!r})"
        )

    if len(selected_cases) == 1:
        selected_case_id, case_cfg = next(iter(selected_cases.items()))
        cfg = deep_merge(defaults, case_cfg)

        paths = prepare_paths(project_root, config_file, selected_case_id, out_dir)
        setup_run_logging(paths.run_dir, verbose=verbose)

        log.info("Selected 1 case = %s", selected_case_id)
        log.info("project_root = %s", paths.project_root)
        log.info("config_file  = %s", paths.config_file)
        log.info("case_id      = %s", selected_case_id)
        log.info("run_dir      = %s", paths.run_dir)

        (paths.run_dir / "config_resolved.yaml").write_text(
            yaml.safe_dump(cfg, sort_keys=False),
            encoding="utf-8",
        )

        metadata = {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "case_id": selected_case_id,
            "config_name": config_name,
            "environment": cfg.get("environment"),
            "git_commit": git_commit_hash(paths.project_root),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        }

        (paths.run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        try:
            run_experiment_from_case(cfg, paths, selected_case_id)
        except Exception:
            log.exception("Experiment crashed (case_id=%s)", selected_case_id)
            raise
        else:
            log.info("Experiment finished OK (case_id=%s)", selected_case_id)

        return

    if out_dir is not None:
        raise ValueError(
            "--out_dir is not supported yet when running multiple cases"
        )

    batch_name = environment or "batch"

    batch_paths = prepare_batch_paths(
        project_root=project_root,
        config_file=config_file,
        batch_name=batch_name,
        out_dir=out_dir,
    )

    setup_run_logging(batch_paths.batch_dir, verbose=verbose)

    log.info(
        "Selected %d case(s): %s",
        len(selected_cases),
        ", ".join(selected_cases.keys()),
    )

    batch_metadata = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "config_name": config_name,
        "filter": {
            "case_id": case_id,
            "environment": environment,
        },
        "selected_cases": len(selected_cases),
        "git_commit": git_commit_hash(batch_paths.batch_dir),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }

    combined_results_db = batch_paths.combined_dir / "results.db"
    results_db_conn = init_db_connection(combined_results_db, create_tables)

    (batch_paths.batch_dir / "batch_metadata.json").write_text(
        json.dumps(batch_metadata, indent=2),
        encoding="utf-8",
    )

    selected_case_id = None
    try:
        for selected_case_id, case_cfg in selected_cases.items():
            cfg = deep_merge(defaults, case_cfg)

            case_paths = prepare_case_paths(
                project_root=project_root,
                config_file=config_file,
                case_id=selected_case_id,
                cases_dir=batch_paths.cases_dir,
            )

            log.info("Running case_id=%s in %s", selected_case_id, case_paths.run_dir)

            (case_paths.run_dir / "config_resolved.yaml").write_text(
                yaml.safe_dump(cfg, sort_keys=False),
                encoding="utf-8",
            )

            case_metadata = {
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                "case_id": selected_case_id,
                "config_name": config_name,
                "environment": cfg.get("environment"),
                "batch_dir": str(batch_paths.batch_dir),
                "git_commit": git_commit_hash(case_paths.project_root),
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            }

            (case_paths.run_dir / "metadata.json").write_text(
                json.dumps(case_metadata, indent=2),
                encoding="utf-8",
            )

            run_experiment_from_case(
                cfg,
                case_paths,
                selected_case_id,
                shared_results_db_conn=results_db_conn,
                shared_results_db_file=combined_results_db,
            )

        results_db_conn.commit()

        export_experiments_to_csv(
            str(combined_results_db),
            str(batch_paths.combined_dir / "experiments.csv"),
        )
        export_experiment_metrics_to_csv(
            str(combined_results_db),
            str(batch_paths.combined_dir / "experiment_metrics.csv"),
        )

    except Exception:
        log.exception("Batch execution crashed (last case_id=%s)", selected_case_id)
        raise
    else:
        log.info("Combined results exported to %s", batch_paths.combined_dir)

    finally:
            results_db_conn.close()
