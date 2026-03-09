from __future__ import annotations

import datetime as dt
import json
import logging
import platform

import sys

from pathlib import Path
from typing import Optional

import yaml

from evac_sim.io.run_paths import prepare_paths, git_commit_hash
from evac_sim.io.config_loader import load_case, deep_merge
from evac_sim.io.logging_setup import setup_run_logging
from evac_sim.orchestration.experiment_runner import run_experiment_from_case

log = logging.getLogger(__name__)

def run_from_yaml(
    *,
    project_root: Path,
    config_name: str,
    case_id: str,
    out_dir: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    project_root = project_root.resolve()

    paths = prepare_paths(project_root, config_name, case_id, out_dir)
    setup_run_logging(paths.run_dir, verbose=verbose)

    defaults_file = project_root / "configs" / "defaults.yaml"
    defaults = {}
    if defaults_file.exists():
        defaults = yaml.safe_load(defaults_file.read_text(encoding="utf-8")) or {}

    case_cfg = load_case(paths.config_file, case_id)
    cfg = deep_merge(defaults, case_cfg)

    log.info("project_root = %s", paths.project_root)
    log.info("config_file  = %s", paths.config_file)
    log.info("case_id      = %s", case_id)
    log.info("run_dir      = %s", paths.run_dir)

    (paths.run_dir / "config_resolved.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8",
    )

    metadata = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "case_id": case_id,
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
        run_experiment_from_case(cfg, paths, case_id)
    except Exception:
        log.exception("Experiment crashed (case_id=%s)", case_id)
        raise
    else:
        log.info("Experiment finished OK (case_id=%s)", case_id)
