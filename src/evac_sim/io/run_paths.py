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

def _make_run_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        if out_dir.exists() and any(out_dir.iterdir()):
            raise FileExistsError(f"Output directory already exists: {out_dir}")
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
    project_root: Path, config_name: str, case_id: str, out_dir: Optional[Path]
) -> RunPaths:
    config_file = project_root / "configs" / config_name
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    run_dir = _make_run_dir(project_root, case_id, out_dir)
    logs_dir = run_dir / "logs"
    artifacts_dir = run_dir / "artifacts"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
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