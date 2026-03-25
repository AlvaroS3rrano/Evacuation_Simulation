from __future__ import annotations

from evac_sim.envs.environment_data.mall import get_mall
from evac_sim.envs.environment_data.cruise_ship import get_cruise_ship
from evac_sim.envs.environment_data.cruise_ship_v2 import get_cruise_ship_v2
from evac_sim.envs.environment_data.theme_park import get_theme_park
from evac_sim.envs.environment_data.simple_3x3 import get_simple_3x3
from evac_sim.envs.environment_data.corridor import get_corridor_environment
from evac_sim.envs.environment_data.comparing_algorithms import get_comparing_algorithms_pol
from evac_sim.envs.environment_data.management_building import get_management_building_basement


ENVIRONMENTS = {
    "comparing_algorithms": get_comparing_algorithms_pol,
    "corridor": get_corridor_environment,
    "cruise_ship": get_cruise_ship,
    "cruise_ship_v2": get_cruise_ship_v2,
    "mall": get_mall,
    "simple_3x3": get_simple_3x3,
    "theme_park": get_theme_park,
    "management_building_basement": get_management_building_basement,
}


def select_environment(name: str):
    try:
        return ENVIRONMENTS[name]()
    except KeyError as exc:
        available = ", ".join(sorted(ENVIRONMENTS))
        raise ValueError(
            f"Unknown environment '{name}'. Available environments: {available}"
        ) from exc