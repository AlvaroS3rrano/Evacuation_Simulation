import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import numpy as np

from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.orchestration.grouping_config import GroupDistributionConfig

@dataclass(frozen=True)
class AgentPositioningConfig:
    distance_to_agents: float
    distance_to_polygon: float
    agent_position_seed: int

@dataclass(frozen=True)
class JuPedSimConfig:
    strength_neighbor_repulsion: float
    range_neighbor_repulsion: float
    range_geometry_repulsion: float


@dataclass(frozen=True)
class ExperimentResources:
    env_name: str
    walkable_area: Any
    obstacles: Any
    targets: list[Any]
    sources: list[Any]
    total_agents: list[int]
    waypoints: dict[Any, Any]
    graph: Any
    specific_areas: dict[Any, Any]
    env_info: EnvironmentInfo
    positions: dict[str, np.ndarray]
    risk_first_frame: dict[Any, float]
    simulation_db_file: Path
    simulation_conn: sqlite3.Connection
    danger_visualization_frame: int | None
    risk_seed: int
    risk_threshold: float
    gamma: float
    stairs_max_speed: float
    normal_max_speed: float
    every_nth_frame_simulation: int
    every_nth_frame_animation: int
    mode_type: int
    modes: list[int]
    agent_positioning: AgentPositioningConfig
    grouping_config: GroupDistributionConfig | None
    jps_config: JuPedSimConfig
    owns_simulation_conn: bool