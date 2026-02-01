from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import statistics
import re
import yaml

def count_agents(agents_section):
    """
    Counts the total number of agents as the sum of values inside agent lists.
    Example:
        [[5, 3], [2]] -> 10
        [5, 3, 2] -> 10
    """
    if not isinstance(agents_section, list):
        return 0

    total = 0
    for group in agents_section:
        if isinstance(group, list):
            total += sum(int(x) for x in group)
        else:
            total += int(group)

    return total


def extract_case_info(case_name: str) -> Tuple[str, Optional[int]]:
    """
    Returns (base_name, case_number or None)
    Example:
      'cruise_ship_case_1' -> ('cruise_ship', 1)
      'cruise_ship_representative' -> ('cruise_ship_representative', None)
    """
    s = str(case_name)
    m = re.search(r"(.*?)[_\s-]*case[_\s-]*(\d+)", s, flags=re.IGNORECASE)
    if m:
        base = m.group(1).rstrip("_- ")
        return base, int(m.group(2))
    return s, None


def _safe_len(x: Any) -> int:
    return len(x) if isinstance(x, list) else 0


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _mean_or_std(values: List[float], stat: str) -> float:
    if not values:
        return 0.0
    if stat == "mean":
        return float(statistics.fmean(values))
    if stat == "std":
        # std poblacional (como suele hacerse en agregaciones rápidas). Si prefieres muestral, dímelo.
        if len(values) < 2:
            return 0.0
        return float(statistics.pstdev(values))
    raise ValueError("stat must be either 'mean' or 'std'.")


def yaml_to_latex_row_env_summary(
    yaml_path: str,
    environment: str,
    stat: str = "mean",          # "mean" o "std"
    float_fmt: str = "{:.2f}",   # formato de cada celda numérica
    label: Optional[str] = None  # cómo quieres que aparezca el environment en la tabla
) -> str:
    """
    Compute aggregated stats across ALL cases in the YAML whose 'environment' matches `environment`
    and return ONE LaTeX row.

    Metrics aggregated over cases:
        - mean number of sources
        - mean number of agents
        - mean number of targets
        - mean of (count(starting_risks) + count(risk_overrides))

    Returns a row like:
        "<Label> & <mean_sources> & <mean_agents> & <mean_targets> & <mean_start_plus_overrides> \\\\"
    """

    if stat not in ("mean", "std"):
        raise ValueError("stat must be either 'mean' or 'std'.")

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f)

    sources_counts: List[float] = []
    agents_counts: List[float] = []
    targets_counts: List[float] = []
    start_plus_over_counts: List[float] = []

    for case_name, cfg in (data or {}).items():
        if not isinstance(cfg, dict):
            continue

        if str(cfg.get("environment", "")).strip() != str(environment).strip():
            continue

        sources_counts.append(float(_safe_len(cfg.get("sources", []))))
        agents_counts.append(float(count_agents(cfg.get("agents", []))))
        targets_counts.append(float(_safe_len(cfg.get("targets", []))))

        starting_risks = cfg.get("starting_risks", [])
        risk_overrides = cfg.get("risk_overrides", [])
        start_plus_over = _safe_len(starting_risks) + _safe_len(risk_overrides)
        start_plus_over_counts.append(float(start_plus_over))

    if not sources_counts:
        raise ValueError(
            f"No cases found for environment='{environment}' in '{yaml_path}'."
        )

    r = {
        "Environment": label if label is not None else str(environment),
        "mean_sources": _mean_or_std(sources_counts, stat),
        "mean_agents": _mean_or_std(agents_counts, stat),
        "mean_targets": _mean_or_std(targets_counts, stat),
        "mean_start_plus_overrides": _mean_or_std(start_plus_over_counts, stat),
    }

    rows: List[str] = []
    rows.append(
        f"{r['Environment']} & "
        f"{float_fmt.format(r['mean_sources'])} & "
        f"{float_fmt.format(r['mean_agents'])} & "
        f"{float_fmt.format(r['mean_targets'])} & "
        f"{float_fmt.format(r['mean_start_plus_overrides'])} \\\\"
    )
    return "\n".join(rows)


if __name__ == "__main__":
    # Ejemplo rápido (ajusta environment a: 'cruise_ship' / 'theme_park' / 'corridor', etc.)
    # y el path al YAML.
    path = "../../../configs/study.yaml"
    env = "cruise_ship"
    print(yaml_to_latex_row_env_summary(path, env, stat="std", float_fmt="{:.2f}"))