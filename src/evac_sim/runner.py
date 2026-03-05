from __future__ import annotations

import datetime as dt
import json
import logging
import platform
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


import jupedsim as jps
import numpy as np
import yaml
import pandas as pd

import evac_sim.envs.environment as pol
from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.environment_info import EnvironmentInfo
from evac_sim.core.risk_simulation_values import RiskSimulationValues
from evac_sim.core.simulation_config import SimulationConfig
from evac_sim.db.danger_sim_db_manager import create_risk_table, get_risk_levels_by_frame
from evac_sim.db.group_path_db_manager import create_group_path_table
from evac_sim.db.paths_db_manager import create_paths_table
from evac_sim.db.simulation_results_db_manager import (
    create_tables,
    write_experiment,
    write_experiment_metrics,
    export_experiments_to_csv,
    export_experiment_metrics_to_csv,
)
from evac_sim.db.agent_area_db_manager import (
    create_agent_area_table,
    read_agent_area_data,
    get_average_normalized_risk_exposure_by_group,
)
from evac_sim.db.group_path_db_manager import read_group_path_data
from evac_sim.envs.journey_configuration import set_journeys
from evac_sim.risk.risk_simulation import simulate_risk
from evac_sim.routing.decision_policies import compute_alternative_path
from evac_sim.simulation.simulation_manager import run_agent_simulation, set_agents_in_simulation

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunPaths:
    project_root: Path
    config_file: Path
    run_dir: Path
    logs_dir: Path
    artifacts_dir: Path


def _git_commit_hash(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"

def _p90(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.array(values, dtype=float), 90))


def _evacuation_times_from_agent_area(agent_area_df: pd.DataFrame) -> dict[int, int]:
    """
    Returns evacuation time per agent as the last frame recorded for that agent.
    If an agent disappears after evacuation, the last recorded frame is a good proxy.
    """
    if agent_area_df.empty:
        return {}
    # last frame per agent
    last_frames = agent_area_df.groupby("agent_id")["frame"].max()
    return {int(agent_id): int(frame) for agent_id, frame in last_frames.items()}


def _compute_group_metrics(
    *,
    group_path_df: pd.DataFrame,
    agent_area_conn: sqlite3.Connection,
    group_id: Any,
    agent_ids: list[int],
    time_step_seconds: float,
    every_nth_frame_simulation: int,
) -> dict[str, Any]:
    """
    Compute metrics for ONE group using:
      - group_path_df: dynamic routing info per frame
      - agent_area_data: per-agent risk time-series

    Note: agent_area frames are recorded every `every_nth_frame_simulation` simulation iterations.
    We convert frame index -> seconds as:
        seconds = frame * every_nth_frame_simulation * time_step_seconds
    """
    # Filter group rows (group_id may be stored as int/str depending on SQLite typing)
    gdf = group_path_df[group_path_df["group_id"].astype(str) == str(group_id)].copy()
    n_records = int(len(gdf))

    # Remaining-path risk estimates over time
    mean_remaining_path_risk = float(gdf["est_risk_mean"].mean()) if n_records else 0.0
    remaining_path_risk_var = float(gdf["est_risk_var"].mean()) if n_records else 0.0

    # Average remaining path length (using next_path decoded by read_group_path_data)
    if n_records and "next_path" in gdf.columns:
        avg_path_length = float(gdf["next_path"].apply(lambda p: len(p) if isinstance(p, list) else 0).mean())
    else:
        avg_path_length = 0.0

    # Risk exposure for this group from agent_area_data
    cumulative_risk_exposure = float(get_average_normalized_risk_exposure_by_group(agent_area_conn, agent_ids))

    # Evacuation time stats (in seconds)
    agent_area_df = read_agent_area_data(agent_area_conn)
    times_map_frames = _evacuation_times_from_agent_area(agent_area_df)

    times_frames = [times_map_frames.get(int(aid)) for aid in agent_ids if int(aid) in times_map_frames]
    times_frames = [t for t in times_frames if t is not None]

    frame_to_seconds = float(every_nth_frame_simulation) * float(time_step_seconds)

    if times_frames:
        times_seconds = [float(t) * frame_to_seconds for t in times_frames]

        min_time = float(min(times_seconds))
        avg_time = float(sum(times_seconds) / len(times_seconds))
        median_time = float(np.median(np.array(times_seconds, dtype=float)))
        p90_time = _p90(times_seconds)
        max_time = float(max(times_seconds))
    else:
        min_time = avg_time = median_time = p90_time = max_time = 0.0

    return {
        "n_records": n_records,
        "mean_remaining_path_risk": mean_remaining_path_risk,
        "remaining_path_risk_var": remaining_path_risk_var,
        "cumulative_risk_exposure": cumulative_risk_exposure,
        "avg_path_length": avg_path_length,
        "min_time": min_time,
        "avg_time": avg_time,
        "median_time": median_time,
        "p90_time": p90_time,
        "max_time": max_time,
    }

def _make_run_dir(project_root: Path, case_id: str, out_dir: Optional[Path]) -> Path:
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    runs_dir = project_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    final = runs_dir / f"{stamp}_{case_id}"
    final.mkdir(parents=True, exist_ok=True)
    return final


def _load_case(config_file: Path, case_id: str) -> dict[str, Any]:
    with config_file.open("r", encoding="utf-8") as f:
        all_configs = yaml.safe_load(f)

    if case_id not in all_configs:
        available = ", ".join(sorted(all_configs.keys()))
        raise KeyError(f"case_id '{case_id}' not found in {config_file}. Available: {available}")

    cfg = all_configs[case_id]
    if not isinstance(cfg, dict):
        raise TypeError(f"case '{case_id}' must be a mapping/dict in YAML")
    return cfg


def _setup_run_logging(run_dir: Path, verbose: bool) -> None:
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "run.log"

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
        force=True,
    )


def _prepare_paths(
    project_root: Path, config_name: str, case_id: str, out_dir: Optional[Path]
) -> RunPaths:
    config_file = project_root / "configs" / config_name
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    run_dir = _make_run_dir(project_root, case_id, out_dir)
    logs_dir = run_dir / "logs"
    artifacts_dir = run_dir / "artifacts"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        project_root=project_root,
        config_file=config_file,
        run_dir=run_dir,
        logs_dir=logs_dir,
        artifacts_dir=artifacts_dir,
    )


def _select_environment(name: str):
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


def _init_db_connection(
    db_file: Path,
    create_fn: Optional[Callable[[sqlite3.Connection], None]] = None,
) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    if create_fn is not None:
        create_fn(conn)
    return conn


def _run_experiment_from_case(cfg: dict[str, Any], paths: RunPaths, case_id: str) -> None:
    # --- Load environment ---
    env = _select_environment(cfg["environment"])

    env_name = env.name
    walkable_area = env.walkable_area
    obstacles = env.obstacles
    targets = cfg["targets"]
    sources = cfg["sources"]
    total_agents = cfg["agents"]
    waypoints = env.waypoints
    G = env.graph
    specific_areas = env.specific_areas

    # --- Modes ---
    mode_type = int(cfg.get("mode_type", 0))
    mode_indices = {
        0: [0, 1, 2, 3],
        1: [0, 1],
        2: [0, 1],
        3: [2, 3],
        4: [2],
    }
    if mode_type not in mode_indices:
        raise ValueError(f"Unsupported mode_type: {mode_type}")
    modes = mode_indices[mode_type]

    awareness_levels_per_group = [0, 1, 0, 1]
    algorithm_per_group = [0, 0, 1, 1]

    # --- Parameters ---
    risk_seed = int(cfg["risk_seed"])
    risk_iterations = int(cfg["risk_iterations"])
    risk_increase_chance = float(cfg["risk_increase_chance"])
    propagation_threshold = float(cfg["propagation_threshold"])
    risk_threshold = float(cfg["risk_threshold"])
    gamma = float(cfg["gamma"])
    stairs_max_speed = float(cfg["stairs_max_speed"])
    normal_max_speed = float(cfg["normal_max_speed"])

    every_nth_frame_simulation = int(cfg["every_nth_frame_simulation"])
    every_nth_frame_animation = int(cfg["every_nth_frame_animation"])

    starting_risks = [tuple(x) for x in (cfg.get("starting_risks", []) or [])]
    risk_overrides = [tuple(x) for x in (cfg.get("risk_overrides", []) or [])]

    # --- Files inside run artifacts ---
    risk_db_file = paths.artifacts_dir / f"{env_name}_risks.db"
    paths_db_file = paths.artifacts_dir / f"{env_name}_paths.db"
    group_paths_db_file = paths.artifacts_dir / f"{env_name}_group_paths.db"
    results_db_file = paths.artifacts_dir / f"{env_name}_results.db"

    # --- DB connections ---
    risk_db_conn = _init_db_connection(risk_db_file, create_risk_table)
    paths_conn = _init_db_connection(paths_db_file, create_paths_table)
    group_path_conn = _init_db_connection(group_paths_db_file, create_group_path_table)
    results_db_conn = _init_db_connection(results_db_file, create_tables)

    # --- Prepare targets/areas ---
    pol.set_targets(targets, env)

    # --- Allocate agent positions per source ---
    positions: dict[str, np.ndarray] = {}
    for i, source in enumerate(sources):
        positions[source] = jps.distribute_by_number(
            polygon=specific_areas[source],
            number_of_agents=total_agents[i],
            distance_to_agents=0.4,
            distance_to_polygon=0.5,
            seed=45131502,
        )

    # --- Risk simulation (random layout always, like notebook) ---
    risk_values = RiskSimulationValues(
        risk_iterations,
        risk_increase_chance,
        propagation_threshold,
        starting_risks,
        risk_overrides,
    )

    log.info("Simulating risks: iterations=%s seed=%s", risk_iterations, risk_seed)
    simulate_risk(
        risk_values,
        every_nth_frame_animation,
        G,
        targets,
        risk_db_conn,
        risk_seed,
    )
    risk_first_frame = get_risk_levels_by_frame(risk_db_conn, 0)

    # --- EnvironmentInfo ---
    env_info = EnvironmentInfo(G, paths_conn, floor_number=env.floor_number)
    if env.floor_number > 1:
        env_info.floors = env.floors
        env_info.floor_connecting_nodes = env.floor_connecting_nodes

    # --- Build simulations per mode ---
    simulations: dict[int, jps.Simulation] = {}
    for mode in modes:
        trajectory_file = paths.artifacts_dir / f"{env_name}_mode_{mode}.sqlite"
        sim = jps.Simulation(
            model=jps.CollisionFreeSpeedModel(
                strength_neighbor_repulsion=2.6,
                range_neighbor_repulsion=0.1,
                range_geometry_repulsion=0.05,
            ),
            geometry=walkable_area.polygon,
            trajectory_writer=jps.SqliteTrajectoryWriter(
                output_file=Path(trajectory_file),
                every_nth_frame=every_nth_frame_simulation,
            ),
        )
        simulations[mode] = sim

    # --- Run per mode ---
    for mode, simulation in simulations.items():
        log.info("Mode start | mode=%s env=%s case=%s", mode, env_name, cfg.get("name", "unknown"))

        # Per-mode DBs (avoid mixing data across modes)
        agent_area_db_file = paths.artifacts_dir / f"agent_area_{env_name}_mode_{mode}.db"
        agent_area_conn = sqlite3.connect(str(agent_area_db_file))
        create_agent_area_table(agent_area_conn)

        group_paths_db_file_mode = paths.artifacts_dir / f"{env_name}_group_paths_mode_{mode}.db"
        group_path_conn_mode = _init_db_connection(group_paths_db_file_mode, create_group_path_table)

        exit_ids: dict[Any, Any] = {}
        for area_id in targets:
            exit_ids[area_id] = simulation.add_exit_stage(specific_areas[area_id])

        waypoints_ids: dict[Any, Any] = {}
        for node, (waypoint, distance) in waypoints.items():
            waypoints_ids[node] = simulation.add_waypoint_stage(waypoint, distance)

        agent_groups: dict[str, AgentGroup] = {}

        for i, source in enumerate(sources):
            if mode_type == 1:
                group = AgentGroup(None, None, None, i, mode)
            else:
                group = AgentGroup(None, None, None, algorithm_per_group[mode], awareness_levels_per_group[mode])

            path = compute_alternative_path(
                targets,
                group,
                env_info,
                source,
                risk_per_node=risk_first_frame,
                gamma=gamma,
            )

            journeys_ids = set_journeys(simulation, source, [path], waypoints_ids, exit_ids)
            journey_id, best_path_source = journeys_ids[source][0]
            next_node = best_path_source[1]
            first_waypoint_id = waypoints_ids[next_node]

            agents = set_agents_in_simulation(
                simulation,
                positions[source],
                journey_id,
                first_waypoint_id,
                normal_max_speed,
            )

            group.path = path
            group.current_nodes = {agent: path[0] for agent in agents}
            group.agents = agents
            agent_groups[source] = group

        sim_cfg = SimulationConfig(
            simulation,
            every_nth_frame_simulation,
            every_nth_frame_animation,
            waypoints_ids,
            exit_ids,
            gamma,
            normal_max_speed,
            stairs_max_speed,
        )

        # Use a fresh risk DB connection per mode (fine)
        risk_db_conn_mode = sqlite3.connect(str(risk_db_file))

        try:
            run_agent_simulation(
                sim_cfg,
                cfg.get("log_every_frames", 10),
                agent_groups,
                env_info,
                risk_db_conn_mode,
                agent_area_conn,
                group_path_conn_mode,
                threshold=risk_threshold,
            )
        except Exception:
            log.exception("Simulation failed | mode=%s", mode)
            raise
        finally:
            risk_db_conn_mode.close()

        # --- Write results ONLY if simulation succeeded ---
        case_name_mode = f"{case_id}_mode_{mode}"

        experiment_id = write_experiment(
            results_db_conn,
            case_name=case_name_mode,
            risk_nodes=targets,
            source_nodes=sources,
            agents_per_source=total_agents,
            random_seed=risk_seed,
        )

        group_path_df = read_group_path_data(group_path_conn_mode)

        for group_id, group in agent_groups.items():
            algorithm = "Centrality" if getattr(group, "algorithm", 0) == 1 else "Efficient"
            awareness = float(getattr(group, "awareness_level", 0))

            time_step_seconds = float(cfg.get("time_step_seconds", 0.03))
            metrics = _compute_group_metrics(
                group_path_df=group_path_df,
                agent_area_conn=agent_area_conn,
                group_id=group_id,
                agent_ids=[int(a) for a in group.agents],
                time_step_seconds=time_step_seconds,
                every_nth_frame_simulation=every_nth_frame_simulation,
            )

            write_experiment_metrics(
                results_db_conn,
                experiment_id=experiment_id,
                case_name=case_name_mode,
                agent_group_id=str(group_id),
                algorithm=algorithm,
                awareness=awareness,
                n_records=metrics["n_records"],
                mean_remaining_path_risk=metrics["mean_remaining_path_risk"],
                remaining_path_risk_var=metrics["remaining_path_risk_var"],
                cumulative_risk_exposure=metrics["cumulative_risk_exposure"],
                avg_path_length=metrics["avg_path_length"],
                avg_time=metrics["avg_time"],
                median_time=metrics["median_time"],
                p90_time=metrics["p90_time"],
                min_time=metrics["min_time"],
                max_time=metrics["max_time"],
            )

    # Ensure results are written
    results_db_conn.commit()

    experiments_csv = paths.artifacts_dir / "experiments.csv"
    metrics_csv = paths.artifacts_dir / "experiment_metrics.csv"

    export_experiments_to_csv(str(results_db_file), str(experiments_csv))
    export_experiment_metrics_to_csv(str(results_db_file), str(metrics_csv))

    log.info("Exported CSV: %s", experiments_csv)
    log.info("Exported CSV: %s", metrics_csv)

    # Close shared DBs
    paths_conn.close()
    risk_db_conn.close()
    results_db_conn.close()

    log.info("Finished mode=%s", mode)

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def run_from_yaml(
    *,
    project_root: Path,
    config_name: str,
    case_id: str,
    out_dir: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    project_root = project_root.resolve()

    paths = _prepare_paths(project_root, config_name, case_id, out_dir)
    _setup_run_logging(paths.run_dir, verbose=verbose)

    defaults_file = project_root / "configs" / "defaults.yaml"
    defaults = {}
    if defaults_file.exists():
        defaults = yaml.safe_load(defaults_file.read_text(encoding="utf-8")) or {}

    case_cfg = _load_case(paths.config_file, case_id)
    cfg = _deep_merge(defaults, case_cfg)

    log.info("project_root = %s", paths.project_root)
    log.info("config_file  = %s", paths.config_file)
    log.info("case_id      = %s", case_id)
    log.info("run_dir      = %s", paths.run_dir)

    (paths.run_dir / "config_resolved.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8",
    )

    metadata = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "case_id": case_id,
        "config_name": config_name,
        "environment": cfg.get("environment"),
        "git_commit": _git_commit_hash(paths.project_root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }

    (paths.run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    try:
        _run_experiment_from_case(cfg, paths, case_id)
    except Exception:
        log.exception("Experiment crashed (case_id=%s)", case_id)
        raise
    else:
        log.info("Experiment finished OK (case_id=%s)", case_id)
