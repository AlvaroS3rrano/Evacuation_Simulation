from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import datetime as dt
import yaml


@dataclass(frozen=True)
class RunPaths:
    project_root: Path
    config_dir: Path
    out_dir: Path
    sqlite_dir: Path


def _make_out_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    runs_dir = project_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final = runs_dir / f"{stamp}_{case_id}"
    final.mkdir(parents=True, exist_ok=True)
    return final


def _load_case(project_root: Path, config_name: str, case_id: str) -> dict:
    config_dir = project_root / "configs"
    config_file = config_dir / config_name
    with config_file.open("r", encoding="utf-8") as f:
        all_configs = yaml.safe_load(f)
    if case_id not in all_configs:
        raise KeyError(f"case_id '{case_id}' not found in {config_file}")
    return all_configs[case_id]


def run_from_yaml(*, project_root: Path, config_name: str, case_id: str, out_dir: Optional[Path] = None) -> None:
    """
    Entry point equivalent to the "happy path" in Notebooks/experiments.ipynb,
    but runnable from terminal.
    """
    project_root = project_root.resolve()
    cfg = _load_case(project_root, config_name, case_id)

    out_dir = _make_out_dir(project_root, case_id, out_dir)

    # --- TODO: traducir aquí el flujo del notebook paso a paso ---
    # Vamos a ir conectando con tus funciones actuales.
    # Por ahora dejamos un "esqueleto" que valida config + crea out_dir.

    # Guardar la config resuelta para reproducibilidad
    (out_dir / "config_resolved.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    print(f"[evac-sim] project_root = {project_root}")
    print(f"[evac-sim] case_id      = {case_id}")
    print(f"[evac-sim] out_dir      = {out_dir}")
    print("[evac-sim] Next: conectar este runner con la simulación (risk/env/db/sim).")