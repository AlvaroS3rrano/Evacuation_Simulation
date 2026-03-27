from __future__ import annotations

import argparse
import matplotlib.pyplot as plt
import pedpy

from evac_sim.envs.environment_factory import select_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize only the walkable area of an environment"
    )
    parser.add_argument(
        "--env",
        default="management_building_floor_0",
        help="Environment name",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    env = select_environment(args.env)
    walkable_area = env.walkable_area

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_aspect("equal")

    pedpy.plot_walkable_area(
        walkable_area=walkable_area,
        axes=ax,
    )

    ax.set_title(f"Walkable area - env={args.env}")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()