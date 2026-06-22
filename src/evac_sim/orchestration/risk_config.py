from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RiskConfig:
    """
    Risk propagation and risk-aware routing configuration.

    The risk block is optional in the YAML. Missing values fall back to these
    defaults or, temporarily, to legacy top-level keys when present.
    """

    enabled: bool = False

    risk_iterations: int = 1500
    risk_increase_chance: float = 0.05
    propagation_threshold: float = 0.5
    risk_threshold: float = 0.5

    starting_risks: list[tuple[str, float]] = field(default_factory=list)
    risk_overrides: list[tuple[int, str, float]] = field(default_factory=list)


def _normalise_starting_risks(raw_values: Any) -> list[tuple[str, float]]:
    return [
        (str(node_id), float(risk))
        for node_id, risk in (raw_values or [])
    ]


def _normalise_risk_overrides(raw_values: Any) -> list[tuple[int, str, float]]:
    return [
        (int(frame), str(node_id), float(risk))
        for frame, node_id, risk in (raw_values or [])
    ]


def _get_value(
    *,
    risk_cfg: Mapping[str, Any],
    legacy_cfg: Mapping[str, Any],
    key: str,
    default: Any,
) -> Any:
    if key in risk_cfg:
        return risk_cfg[key]

    return legacy_cfg.get(key, default)


def build_risk_config(
    cfg: Mapping[str, Any],
) -> RiskConfig:
    """
    Build risk configuration from the optional `risk` YAML block.

    During the migration, legacy top-level keys are still accepted as fallback:
      - risk_iterations
      - risk_increase_chance
      - propagation_threshold
      - risk_threshold
      - starting_risks
      - risk_overrides
    """
    risk_cfg = cfg.get("risk", {})

    if risk_cfg is None:
        risk_cfg = {}

    if not isinstance(risk_cfg, Mapping):
        raise TypeError("risk must be a mapping when provided")

    enabled = bool(_get_value(
        risk_cfg=risk_cfg,
        legacy_cfg=cfg,
        key="enabled",
        default=False,
    ))

    risk_iterations = int(_get_value(
        risk_cfg=risk_cfg,
        legacy_cfg=cfg,
        key="risk_iterations",
        default=1500,
    ))

    risk_increase_chance = float(_get_value(
        risk_cfg=risk_cfg,
        legacy_cfg=cfg,
        key="risk_increase_chance",
        default=0.05,
    ))

    propagation_threshold = float(_get_value(
        risk_cfg=risk_cfg,
        legacy_cfg=cfg,
        key="propagation_threshold",
        default=0.5,
    ))

    risk_threshold = float(_get_value(
        risk_cfg=risk_cfg,
        legacy_cfg=cfg,
        key="risk_threshold",
        default=0.5,
    ))

    if risk_iterations < 0:
        raise ValueError("risk.risk_iterations must be >= 0")

    if not 0.0 <= risk_increase_chance <= 1.0:
        raise ValueError("risk.risk_increase_chance must be between 0 and 1")

    if not 0.0 <= propagation_threshold <= 1.0:
        raise ValueError("risk.propagation_threshold must be between 0 and 1")

    if not 0.0 <= risk_threshold <= 1.0:
        raise ValueError("risk.risk_threshold must be between 0 and 1")

    starting_risks = _normalise_starting_risks(
        _get_value(
            risk_cfg=risk_cfg,
            legacy_cfg=cfg,
            key="starting_risks",
            default=[],
        )
    )

    risk_overrides = _normalise_risk_overrides(
        _get_value(
            risk_cfg=risk_cfg,
            legacy_cfg=cfg,
            key="risk_overrides",
            default=[],
        )
    )

    return RiskConfig(
        enabled=enabled,
        risk_iterations=risk_iterations,
        risk_increase_chance=risk_increase_chance,
        propagation_threshold=propagation_threshold,
        risk_threshold=risk_threshold,
        starting_risks=starting_risks,
        risk_overrides=risk_overrides,
    )