from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_METRICS_CONFIG = PROJECT_ROOT / "configs" / "metrics" / "default_metrics.yaml"


def deep_merge(base: dict[str, Any], override: Mapping[str, Any] | None) -> dict[str, Any]:
    """Recursively merge two dictionaries without mutating either input."""
    result = deepcopy(base)

    if not override:
        return result

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, Mapping)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Metrics config not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Metrics config must be a YAML mapping: {path}")

    return data


def load_metrics_config(
    *,
    config_path: str | Path | None = None,
    case_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load the default metrics config and apply optional case overrides.

    The intended usage is:
      1. Keep a project-wide default YAML in configs/metrics/default_metrics.yaml.
      2. Add a `metrics:` section only in scenarios that need different settings.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_METRICS_CONFIG

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    default_config = load_yaml(path)
    return deep_merge(default_config, case_override)


def metrics_override_from_case(case_cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    if not case_cfg:
        return {}

    override = case_cfg.get("metrics", {})

    if override is None:
        return {}

    if not isinstance(override, dict):
        raise ValueError("case metrics override must be a mapping")

    return override
