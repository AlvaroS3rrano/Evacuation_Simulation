import subprocess
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class RunPaths:
    project_root: Path
    config_file: Path
    run_dir: Path
    logs_dir: Path
    artifacts_dir: Path
    images_dir: Path
    db_dir: Path
    csv_dir: Path

@dataclass(frozen=True)
class BatchPaths:
    project_root: Path
    config_file: Path
    batch_dir: Path
    cases_dir: Path
    combined_dir: Path
    logs_dir: Path

def make_run_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        if out_dir.exists() and any(out_dir.iterdir()):
            raise FileExistsError(
                f"Output directory must be empty: {out_dir}"
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    safe_case_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in case_id)
    runs_dir = project_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    final = runs_dir / f"{stamp}_{safe_case_id}"
    final.mkdir(parents=True, exist_ok=True)
    return final

def prepare_paths(
    project_root: Path, config_file: Path, case_id: str, out_dir: Optional[Path]
) -> RunPaths:

    run_dir = make_run_dir(project_root, case_id, out_dir)
    logs_dir = run_dir / "logs"
    artifacts_dir = run_dir / "artifacts"
    images_dir = artifacts_dir / "images"
    db_dir = artifacts_dir / "db"
    csv_dir = artifacts_dir / "csv"

    for d in (logs_dir, artifacts_dir, images_dir, db_dir, csv_dir):
        d.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
        images_dir=images_dir,
        db_dir=db_dir,
        csv_dir=csv_dir,
    )

def prepare_batch_paths(
        project_root: Path,
        config_file: Path,
        batch_name: str,
        out_dir: Optional[Path],
) -> BatchPaths:
    batch_dir = make_run_dir(project_root, batch_name, out_dir)

    cases_dir = batch_dir / "cases"
    combined_dir = batch_dir / "combined"
    logs_dir = batch_dir / "logs"

    for d in (cases_dir, combined_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    return BatchPaths(
        project_root=project_root,
        config_file=config_file,
        batch_dir=batch_dir,
        cases_dir=cases_dir,
        combined_dir=combined_dir,
        logs_dir=logs_dir,
    )

def prepare_case_paths(
        project_root: Path,
        config_file: Path,
        case_id: str,
        cases_dir: Path,
) -> RunPaths:
    safe_case_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in case_id)

    run_dir = cases_dir / safe_case_id
    logs_dir = run_dir / "logs"
    artifacts_dir = run_dir / "artifacts"
    images_dir = artifacts_dir / "images"
    db_dir = artifacts_dir / "db"
    csv_dir = artifacts_dir / "csv"

    for d in (run_dir, logs_dir, artifacts_dir, images_dir, db_dir, csv_dir):
        d.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
        images_dir=images_dir,
        db_dir=db_dir,
        csv_dir=csv_dir,
    )

def git_commit_hash(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"