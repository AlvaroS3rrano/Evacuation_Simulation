import yaml
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

def load_case(config_file: Path, case_id: str) -> dict[str, Any]:
    with config_file.open("r", encoding="utf-8") as f:
        all_configs = yaml.safe_load(f)

    if case_id not in all_configs:
        available = ", ".join(sorted(all_configs.keys()))
        raise KeyError(f"case_id '{case_id}' not found in {config_file}. Available: {available}")

    cfg = all_configs[case_id]
    if not isinstance(cfg, dict):
        raise TypeError(f"case '{case_id}' must be a mapping/dict in YAML")
    return cfg

def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    log.debug("Final config: %s", out)
    return out