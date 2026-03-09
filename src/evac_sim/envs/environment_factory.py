import evac_sim.envs.environment as pol

def select_environment(name: str):
    environments = {
        "cruise_ship": pol.get_cruise_ship,
        "cruise_ship_v2": pol.get_cruise_ship_v2,
        "mall": pol.get_mall,
        "theme_park": pol.get_theme_park,
        "simple_3x3": pol.get_simple_3x3,
        "comparing_algorithms": pol.get_comparing_algorithms_pol,
        "corridor": pol.get_corridor_environment,
    }
    if name not in environments:
        raise ValueError(f"Unknown environment '{name}'. Available: {list(environments.keys())}")
    return environments[name]()