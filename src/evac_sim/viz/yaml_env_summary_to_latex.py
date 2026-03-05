from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


def count_agents(agents_section: Any) -> int:
    """
    Counts the total number of agents as the sum of values inside agent lists.
    Examples:
        [[5, 3], [2]] -> 10
        [5, 3, 2]     -> 10
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
    Returns (base_name, case_number or None).

    Examples:
      'cruise_ship_case_1'          -> ('cruise_ship', 1)
      'cruise_ship_representative'  -> ('cruise_ship_representative', None)
    """
    s = str(case_name)
    m = re.search(r"(.*?)[_\s-]*case[_\s-]*(\d+)", s, flags=re.IGNORECASE)
    if not m:
        return s, None
    base = m.group(1).rstrip("_- ")
    return base, int(m.group(2))


def _safe_len(x: Any) -> int:
    """Returns len(x) if x is a list, otherwise 0."""
    return len(x) if isinstance(x, list) else 0


def _mean(values: List[float]) -> float:
    """Arithmetic mean with safe empty-list handling."""
    return float(statistics.fmean(values)) if values else 0.0


def _std_pop(values: List[float]) -> float:
    """Population standard deviation (pstdev), safe for small lists."""
    if not values or len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values))


def _format_cell(mean_v: float, std_v: float, mode: str, fmt: str) -> str:
    """
    Formats a cell according to mode:
      - mean      -> fmt(mean)
      - std       -> fmt(std)
      - mean+std  -> $fmt(mean) \\pm fmt(std)$
    """
    if mode == "mean":
        return fmt.format(mean_v)
    if mode == "std":
        return fmt.format(std_v)
    # mean ± std
    return f"${fmt.format(mean_v)} \\pm {fmt.format(std_v)}$"


def _load_yaml(yaml_path: str) -> Dict[str, Any]:
    """Loads YAML once and returns the parsed dict."""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}


def _collect_env_metrics(data: Dict[str, Any], environment: str) -> Dict[str, List[float]]:
    """
    Collects per-case metric values for a given environment.
    Returns lists (one value per case) for each metric.
    """
    env_key = str(environment).strip()

    sources: List[float] = []
    agents: List[float] = []
    targets: List[float] = []
    start_plus_over: List[float] = []

    for _, cfg in data.items():
        if not isinstance(cfg, dict):
            continue
        if str(cfg.get("environment", "")).strip() != env_key:
            continue

        sources.append(float(_safe_len(cfg.get("sources", []))))
        agents.append(float(count_agents(cfg.get("agents", []))))
        targets.append(float(_safe_len(cfg.get("targets", []))))

        starting_risks = cfg.get("starting_risks", [])
        risk_overrides = cfg.get("risk_overrides", [])
        start_plus_over.append(float(_safe_len(starting_risks) + _safe_len(risk_overrides)))

    if not sources:
        raise ValueError(f"No cases found for environment='{environment}' in the provided YAML.")

    return {
        "sources": sources,
        "agents": agents,
        "targets": targets,
        "start_plus_overrides": start_plus_over,
    }


def yaml_to_latex_rows_env_summary(
    yaml_path: str,
    environments: Iterable[str],
    mode: str = "mean",  # "mean", "std", "mean+std"
    float_fmt: str = "{:.2f}",  # formatting for numeric cells
    labels: Optional[Dict[str, str]] = None,  # optional mapping env -> label
    do_print: bool = False,
) -> str:
    """
    Builds LaTeX rows (one per environment) aggregating across ALL cases in the YAML.

    Aggregated metrics over cases:
      - number of sources
      - number of agents
      - number of targets
      - (count(starting_risks) + count(risk_overrides))

    Modes:
      - "mean":     prints only the mean
      - "std":      prints only the std (population std)
      - "mean+std": prints '$mean \\pm std$' per cell
    """
    mode = str(mode).strip().lower()
    mean_pm_aliases = {"mean+std", "mean±std", "mean_pm_std", "meanpmstd"}
    valid = {"mean", "std"} | mean_pm_aliases
    if mode not in valid:
        raise ValueError("mode must be one of: 'mean', 'std', 'mean+std'.")

    # Normalize mode aliases
    if mode in mean_pm_aliases:
        mode = "mean+std"

    data = _load_yaml(yaml_path)

    rows: List[str] = []
    for env in environments:
        m = _collect_env_metrics(data, env)

        # Compute mean/std once per metric
        sources_mean, sources_std = _mean(m["sources"]), _std_pop(m["sources"])
        agents_mean, agents_std = _mean(m["agents"]), _std_pop(m["agents"])
        targets_mean, targets_std = _mean(m["targets"]), _std_pop(m["targets"])
        spo_mean, spo_std = _mean(m["start_plus_overrides"]), _std_pop(m["start_plus_overrides"])

        label = labels.get(env, str(env)) if labels else str(env)

        row = (
            f"{label} & "
            f"{_format_cell(sources_mean, sources_std, mode, float_fmt)} & "
            f"{_format_cell(agents_mean, agents_std, mode, float_fmt)} & "
            f"{_format_cell(targets_mean, targets_std, mode, float_fmt)} & "
            f"{_format_cell(spo_mean, spo_std, mode, float_fmt)} \\\\"
        )
        rows.append(row)

    result = "\n".join(rows)
    if do_print:
        print(result)
    return result


if __name__ == "__main__":
    path = "../../../configs/study.yaml"

    envs = ["cruise_ship", "theme_park", "corridor"]
    mode = "mean+std"  # "mean", "std", "mean+std"

    labels = {
        "cruise_ship": "Cruise Ship",
        "theme_park": "Theme Park",
        "corridor": "Corridor",
    }

    yaml_to_latex_rows_env_summary(path, envs, mode=mode, labels=labels, do_print=True)
