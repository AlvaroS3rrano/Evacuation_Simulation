from __future__ import annotations

import random
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jupedsim as jps
import yaml

from evac_sim.envs.environment_factory import select_environment
from evac_sim.io.config_loader import deep_merge

from tools.random_experiments.scenario_space import (
    EFFICIENT_HIGH_MODE_TYPE,
    SCENARIOS,
    ScenarioSpec,
)


@dataclass(frozen=True)
class RandomCaseGenerationSettings:
    configs_per_scenario: int
    master_seed: int

    agents_per_source_min: int
    agents_per_source_max: int

    sources_per_case_min: int
    sources_per_case_max: int

    targets_per_case_min: int
    targets_per_case_max: int

    include_base_config: bool = False


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")

    return data


def write_yaml_mapping(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def _ensure_non_selected_targets_are_waypoints(
    *,
    case_cfg: dict[str, Any],
    scenario: ScenarioSpec,
) -> None:
    """
    Selected targets are exits.

    Possible targets that were NOT selected in this generated case must remain
    traversable as JuPedSim waypoints. Otherwise, paths that pass through one of
    those nodes before reaching the selected exit cannot be converted into a
    valid JuPedSim journey.
    """
    selected_targets = {
        str(target)
        for target in case_cfg.get("targets", [])
    }

    existing_waypoints = [
        str(waypoint)
        for waypoint in case_cfg.get("waypoints", [])
    ]

    non_selected_target_waypoints = [
        str(target)
        for target in scenario.possible_targets
        if str(target) not in selected_targets
    ]

    case_cfg["waypoints"] = list(
        dict.fromkeys(
            [
                *existing_waypoints,
                *non_selected_target_waypoints,
            ]
        )
    )


def _sample_amount(
    rng: random.Random,
    *,
    minimum: int,
    maximum: int,
    available: int,
) -> int:
    minimum = max(1, minimum)
    maximum = min(maximum, available)

    if maximum < minimum:
        maximum = minimum

    return rng.randint(minimum, maximum)


def _extract_placeable_agents_from_error(exc: Exception) -> int | None:
    """
    Extracts the number of agents JuPedSim says it could place.

    Example error:
        AgentNumberError('Only 70 of 76 could be placed. density: 2.8 p/m²')

    Returns:
        70
    """
    message = str(exc)

    match = re.search(
        r"Only\s+(\d+)\s+of\s+\d+\s+could be placed",
        message,
    )

    if not match:
        return None

    return int(match.group(1))


def _agent_position_seed_from_master_seed(master_seed: int) -> int:
    """
    Reproduces the agent placement seed derived from master_seed.

    The experiment setup first generates a risk seed and then an agent
    position seed. We need the same seed here so that the pre-validation
    matches the real simulation placement.
    """
    master_rng = random.Random(master_seed)

    _risk_seed = master_rng.randint(0, 2**32 - 1)
    agent_position_seed = master_rng.randint(0, 2**32 - 1)

    return agent_position_seed


def _try_place_agents(
    *,
    environment_name: str,
    source_node: str,
    number_of_agents: int,
    distance_to_agents: float,
    distance_to_polygon: float,
    seed: int,
) -> tuple[bool, int | None]:
    """
    Tries to place agents in a source area.

    Returns:
        (True, placed_agents) if all requested agents could be placed.
        (False, placed_hint) if JuPedSim says only a smaller amount fits.
        (False, None) if placement failed without a useful hint.
    """
    if number_of_agents <= 0:
        return True, 0

    env = select_environment(environment_name)

    if source_node not in env.specific_areas:
        raise KeyError(
            f"Source node {source_node!r} is not available in "
            f"environment {environment_name!r}"
        )

    try:
        positions = jps.distribute_by_number(
            polygon=env.specific_areas[source_node],
            number_of_agents=number_of_agents,
            distance_to_agents=distance_to_agents,
            distance_to_polygon=distance_to_polygon,
            seed=seed,
        )
    except Exception as exc:
        placed_hint = _extract_placeable_agents_from_error(exc)
        return False, placed_hint

    placed_agents = len(positions)

    return placed_agents == number_of_agents, placed_agents


def _max_placeable_agents(
    *,
    environment_name: str,
    source_node: str,
    requested_agents: int,
    distance_to_agents: float,
    distance_to_polygon: float,
    seed: int,
) -> int:
    """
    Finds the maximum number of agents that JuPedSim can place in this source area.

    If JuPedSim returns an error like:
        Only 70 of 76 could be placed

    this function tries to use 70 directly. If that still does not fit, it
    falls back to binary search.
    """
    if requested_agents <= 0:
        return 0

    fits, placed_hint = _try_place_agents(
        environment_name=environment_name,
        source_node=source_node,
        number_of_agents=requested_agents,
        distance_to_agents=distance_to_agents,
        distance_to_polygon=distance_to_polygon,
        seed=seed,
    )

    if fits:
        return requested_agents

    if placed_hint is not None and placed_hint > 0:
        hint_fits, _ = _try_place_agents(
            environment_name=environment_name,
            source_node=source_node,
            number_of_agents=placed_hint,
            distance_to_agents=distance_to_agents,
            distance_to_polygon=distance_to_polygon,
            seed=seed,
        )

        if hint_fits:
            return placed_hint

        high = placed_hint
    else:
        high = requested_agents

    low = 0

    while low < high:
        mid = (low + high + 1) // 2

        fits, _ = _try_place_agents(
            environment_name=environment_name,
            source_node=source_node,
            number_of_agents=mid,
            distance_to_agents=distance_to_agents,
            distance_to_polygon=distance_to_polygon,
            seed=seed,
        )

        if fits:
            low = mid
        else:
            high = mid - 1

    return low


def _adjust_agents_to_fit(
    *,
    case_cfg: dict[str, Any],
    defaults: dict[str, Any],
    placement_seed: int,
) -> tuple[list[str], list[int], list[dict[str, Any]]]:
    """
    Validates each selected origin node against JuPedSim.

    If too many agents were requested for an origin area, the number is lowered.
    If no agent can be placed in an origin, that origin is removed from the case.
    """
    resolved_cfg = deep_merge(defaults, case_cfg)

    environment_name = str(resolved_cfg["environment"])
    sources = [str(source) for source in resolved_cfg["sources"]]
    requested_agents = [int(value) for value in resolved_cfg["agents"]]

    distance_to_agents = float(resolved_cfg.get("distance_to_agents", 0.4))
    distance_to_polygon = float(resolved_cfg.get("distance_to_polygon", 0.5))

    adjusted_sources: list[str] = []
    adjusted_agents: list[int] = []
    capacity_report: list[dict[str, Any]] = []

    for index, source_node in enumerate(sources):
        requested = requested_agents[index]

        placed = _max_placeable_agents(
            environment_name=environment_name,
            source_node=source_node,
            requested_agents=requested,
            distance_to_agents=distance_to_agents,
            distance_to_polygon=distance_to_polygon,
            seed=placement_seed,
        )

        capacity_report.append(
            {
                "source": source_node,
                "requested_agents": requested,
                "placed_agents": placed,
                "reduced": placed < requested,
            }
        )

        if placed > 0:
            adjusted_sources.append(source_node)
            adjusted_agents.append(placed)

    if not adjusted_sources:
        raise RuntimeError(
            "JuPedSim could not place agents in any selected source node. "
            f"Case config: {case_cfg}"
        )

    return adjusted_sources, adjusted_agents, capacity_report


def _build_base_case(
    *,
    scenario: ScenarioSpec,
    template_case: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """
    Builds the original base case from congestion_heuristics.yaml.

    This case is not randomized. It preserves the original sources,
    targets, agents and seeds from the template case.

    It only forces mode_type = 5 to ensure all experiments are efficient-high.
    """
    case_cfg = deepcopy(template_case)

    case_cfg["environment"] = scenario.environment
    case_cfg["mode_type"] = EFFICIENT_HIGH_MODE_TYPE

    _ensure_non_selected_targets_are_waypoints(
        case_cfg=case_cfg,
        scenario=scenario,
    )

    case_cfg["random_experiment"] = {
        "scenario": scenario.key,
        "config_index": 1,
        "mode_type": EFFICIENT_HIGH_MODE_TYPE,
        "mode_label": "efficient_high",
        "is_base_config": True,
        "source_template_case_id": scenario.template_case_id,
        "description": (
            "Base case copied from congestion_heuristics.yaml without randomization."
        ),
        "final_sources": case_cfg.get("sources", []),
        "final_targets": case_cfg.get("targets", []),
        "final_agents": case_cfg.get("agents", []),
        "waypoints_added_from_non_selected_targets": case_cfg.get("waypoints", []),
    }

    case_id = f"base_{scenario.key}"

    return case_id, case_cfg


def _build_random_case(
    *,
    scenario: ScenarioSpec,
    template_case: dict[str, Any],
    defaults: dict[str, Any],
    config_index: int,
    settings: RandomCaseGenerationSettings,
    rng: random.Random,
) -> tuple[str, dict[str, Any]]:
    """
    Builds one random efficient-high case.

    Randomized:
    - simulation master_seed
    - grouping seed
    - selected source nodes
    - selected target nodes
    - requested agents per selected source

    Fixed:
    - mode_type = 5, efficient high
    - scenario template structure
    """
    case_seed = rng.randint(0, 2**32 - 1)
    grouping_seed = rng.randint(0, 2**32 - 1)
    agent_position_seed = _agent_position_seed_from_master_seed(case_seed)

    number_of_sources = _sample_amount(
        rng,
        minimum=settings.sources_per_case_min,
        maximum=settings.sources_per_case_max,
        available=len(scenario.possible_sources),
    )

    number_of_targets = _sample_amount(
        rng,
        minimum=settings.targets_per_case_min,
        maximum=settings.targets_per_case_max,
        available=len(scenario.possible_targets),
    )

    selected_sources = rng.sample(
        scenario.possible_sources,
        number_of_sources,
    )

    selected_targets = rng.sample(
        scenario.possible_targets,
        number_of_targets,
    )

    requested_agents = [
        rng.randint(
            settings.agents_per_source_min,
            settings.agents_per_source_max,
        )
        for _ in selected_sources
    ]

    case_cfg = deepcopy(template_case)

    case_cfg["environment"] = scenario.environment
    case_cfg["sources"] = selected_sources
    case_cfg["agents"] = requested_agents
    case_cfg["targets"] = selected_targets

    _ensure_non_selected_targets_are_waypoints(
        case_cfg=case_cfg,
        scenario=scenario,
    )

    # IMPORTANT:
    # All simulations are efficient high.
    case_cfg["mode_type"] = EFFICIENT_HIGH_MODE_TYPE

    case_cfg["master_seed"] = case_seed

    grouping = deepcopy(case_cfg.get("grouping", {}))

    if isinstance(grouping, dict):
        grouping["seed"] = grouping_seed
        case_cfg["grouping"] = grouping

    adjusted_sources, adjusted_agents, capacity_report = _adjust_agents_to_fit(
        case_cfg=case_cfg,
        defaults=defaults,
        placement_seed=agent_position_seed,
    )

    case_cfg["sources"] = adjusted_sources
    case_cfg["agents"] = adjusted_agents

    case_cfg["random_experiment"] = {
        "scenario": scenario.key,
        "config_index": config_index,
        "mode_type": EFFICIENT_HIGH_MODE_TYPE,
        "mode_label": "efficient_high",
        "case_seed": case_seed,
        "grouping_seed": grouping_seed,
        "agent_position_seed": agent_position_seed,
        "requested_sources": selected_sources,
        "requested_targets": selected_targets,
        "requested_agents": requested_agents,
        "final_sources": adjusted_sources,
        "final_targets": selected_targets,
        "final_agents": adjusted_agents,
        "capacity_report": capacity_report,
        "waypoints_added_from_non_selected_targets": case_cfg.get("waypoints", []),
    }

    case_id = f"random_{scenario.key}_{config_index:03d}"

    return case_id, case_cfg


def build_random_cases(
    *,
    base_cases: dict[str, Any],
    defaults: dict[str, Any],
    settings: RandomCaseGenerationSettings,
    scenario_keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    rng = random.Random(settings.master_seed)

    selected_scenarios = scenario_keys or list(SCENARIOS.keys())
    generated_cases: dict[str, dict[str, Any]] = {}

    for scenario_key in selected_scenarios:
        if scenario_key not in SCENARIOS:
            raise ValueError(
                f"Unknown scenario {scenario_key!r}. "
                f"Available scenarios: {', '.join(SCENARIOS)}"
            )

        scenario = SCENARIOS[scenario_key]

        if scenario.template_case_id not in base_cases:
            raise KeyError(
                f"Template case {scenario.template_case_id!r} not found "
                f"in base config."
            )

        template_case = base_cases[scenario.template_case_id]

        first_random_index = 1

        if settings.include_base_config:
            base_case_id, base_case_cfg = _build_base_case(
                scenario=scenario,
                template_case=template_case,
            )

            generated_cases[base_case_id] = base_case_cfg
            first_random_index = 2

        random_configs_to_generate = settings.configs_per_scenario

        if settings.include_base_config:
            random_configs_to_generate = max(
                0,
                settings.configs_per_scenario - 1,
            )

        for offset in range(random_configs_to_generate):
            config_index = first_random_index + offset

            case_id, case_cfg = _build_random_case(
                scenario=scenario,
                template_case=template_case,
                defaults=defaults,
                config_index=config_index,
                settings=settings,
                rng=rng,
            )

            generated_cases[case_id] = case_cfg

    return generated_cases