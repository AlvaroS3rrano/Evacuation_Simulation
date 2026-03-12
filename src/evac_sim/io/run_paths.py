import subprocess
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterable


RUNS_DIRNAME = "runs"
SAFE_CHARS = {"-", "_"}


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

def _sanitize_name(value: str) -> str:
    sanitized =  "".join(
        char if char.isalnum() or char in SAFE_CHARS else "_"
        for char in value.strip()
    )
    if not sanitized:
        raise ValueError(f"Name cannot be empty")
    return sanitized

def _ensure_dirs(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)

def _build_run_paths(project_root: Path, config_file: Path, run_dir: Path) -> RunPaths:
    artifacts_dir = run_dir / "artifacts"

    paths = RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=run_dir / "logs",
        artifacts_dir=artifacts_dir,
        images_dir=artifacts_dir / "images",
        db_dir=artifacts_dir / "db",
        csv_dir=artifacts_dir / "csv",
    )

    _ensure_dirs(
        (
            paths.run_dir,
            paths.logs_dir,
            paths.artifacts_dir,
            paths.images_dir,
            paths.db_dir,
            paths.csv_dir,
        )
    )
    return paths

def _build_batch_paths(project_root: Path, config_file: Path, batch_dir: Path) -> BatchPaths:
    paths = BatchPaths(
        project_root=project_root,
        config_file=config_file,
        batch_dir=batch_dir,
        cases_dir=batch_dir / "cases",
        combined_dir=batch_dir / "combined",
        logs_dir=batch_dir / "logs",
    )

    _ensure_dirs(
        (
            paths.batch_dir,
            paths.cases_dir,
            paths.combined_dir,
            paths.logs_dir,
        )
    )
    return paths


def make_run_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        if out_dir.exists() and any(out_dir.iterdir()):
            raise FileExistsError(
                f"Output directory must be empty: {out_dir}"
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    runs_dir = project_root / RUNS_DIRNAME
    runs_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    safe_case_id = _sanitize_name(case_id)

    final = runs_dir / f"{stamp}_{safe_case_id}"
    final.mkdir(parents=True, exist_ok=True)
    return final

def prepare_paths(
    project_root: Path, config_file: Path, case_id: str, out_dir: Optional[Path]
) -> RunPaths:

    run_dir = make_run_dir(project_root, case_id, out_dir)
    return _build_run_paths(project_root, config_file, run_dir)

def prepare_batch_paths(
        project_root: Path,
        config_file: Path,
        batch_name: str,
        out_dir: Optional[Path],
) -> BatchPaths:
    batch_dir = make_run_dir(project_root, batch_name, out_dir)
    return _build_batch_paths(project_root, config_file, batch_dir)

def prepare_case_paths(
        project_root: Path,
        config_file: Path,
        case_id: str,
        cases_dir: Path,
) -> RunPaths:
    run_dir = cases_dir / _sanitize_name(case_id)
    return _build_run_paths(project_root, config_file, run_dir)

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