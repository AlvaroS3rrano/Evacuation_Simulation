from __future__ import annotations

import gc
import logging
import sqlite3
from pathlib import Path
from typing import Any

import jupedsim as jps

from evac_sim.analysis.metrics import compute_group_metrics
from evac_sim.core.agent_group import AgentGroup
from evac_sim.core.simulation_config import SimulationConfig
from evac_sim.db.exporters.experiments_csv import (
    export_experiment_metrics_to_csv,
    export_experiments_to_csv,
)
from evac_sim.db.repositories.experiments import (
    ExperimentConfig,
    ExperimentMetrics,
    upsert_experiment,
    upsert_experiment_metrics,
)
from evac_sim.db.repositories.group_decisions import get_group_decisions_dataframe
from evac_sim.db.sqlite_utils import compute_times_from_trajectory_sqlite
from evac_sim.io.run_paths import RunPaths
from evac_sim.simulation.simulation_manager import run_agent_simulation
from evac_sim.viz.plots import generate_mode_visual_artifacts

from .experiment_models import (
    AgentPositioningConfig,
    ExperimentResources,
    JuPedSimConfig,
)
from .experiment_setup import (
    build_agent_groups,
    prepare_shared_resources,
)

log = logging.getLogger(__name__)

def create_simulation(
    *,
    walkable_area: Any,
    trajectory_file: Path,
    every_nth_frame_simulation: int,
    strength_neighbor_repulsion: float,
    range_neighbor_repulsion: float,
    range_geometry_repulsion: float,
) -> jps.Simulation:
    return jps.Simulation(
        model=jps.CollisionFreeSpeedModel(
            strength_neighbor_repulsion=strength_neighbor_repulsion,
            range_neighbor_repulsion=range_neighbor_repulsion,
            range_geometry_repulsion=range_geometry_repulsion,
        ),
        geometry=walkable_area.polygon,
        trajectory_writer=jps.SqliteTrajectoryWriter(
            output_file=Path(trajectory_file),
            every_nth_frame=every_nth_frame_simulation,
        ),
    )


def create_stages(
    *,
    simulation: jps.Simulation,
    targets: list[Any],
    specific_areas: dict[Any, Any],
    waypoints: dict[Any, Any],
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    exit_ids: dict[Any, Any] = {}
    for area_id in targets:
        exit_ids[area_id] = simulation.add_exit_stage(specific_areas[area_id])

    waypoints_ids: dict[Any, Any] = {}
    for node, (waypoint, distance) in waypoints.items():
        waypoints_ids[node] = simulation.add_waypoint_stage(waypoint, distance)

    return exit_ids, waypoints_ids


def write_mode_results(
    *,
    case_id: str,
    mode: int,
    graph: Any,
    simulation_conn: sqlite3.Connection,
    trajectory_file: Path,
    risk_seed: int,
    targets: list[Any],
    sources: list[Any],
    total_agents: list[int],
    agent_groups: dict[str, AgentGroup],
) -> None:
    case_name_mode = f"{case_id}_mode_{mode}"

    experiment = ExperimentConfig(
        case_name=case_name_mode,
        risk_nodes=targets,
        source_nodes=sources,
        agents_per_source=total_agents,
        random_seed=risk_seed,
    )

    experiment_id = upsert_experiment(
        simulation_conn,
        experiment,
    )

    group_path_df = get_group_decisions_dataframe(
        simulation_conn,
        case_id,
        mode,
    )

    for group_id, group in agent_groups.items():
        algorithm = "Centrality" if getattr(group, "algorithm", 0) == 1 else "Efficient"
        awareness = float(getattr(group, "awareness_level", 0))

        initial_agents_ids = [
            int(a) for a in getattr(group, "initial_agents_ids", group.agents)
        ]

        per_agent_times = compute_times_from_trajectory_sqlite(
            trajectory_db_file=trajectory_file,
            agent_ids=initial_agents_ids,
        )

        metrics = compute_group_metrics(
            graph=graph,
            group_path_df=group_path_df,
            agent_area_conn=simulation_conn,
            case_name=case_id,
            mode=mode,
            group_id=group_id,
            agent_ids=initial_agents_ids,
            per_agent_times=per_agent_times,
        )

        log.info(
            "Metrics preview | mode=%s group=%s agents=%d min=%.3f avg=%.3f median=%.3f p90=%.3f max=%.3f",
            mode,
            group_id,
            len(initial_agents_ids),
            metrics["min_time"],
            metrics["avg_time"],
            metrics["median_time"],
            metrics["p90_time"],
            metrics["max_time"],
        )

        experiment_metrics = ExperimentMetrics(
            experiment_id=experiment_id,
            agent_group_id=str(group_id),
            algorithm=algorithm,
            awareness=awareness,
            n_records=metrics["n_records"],
            mean_remaining_path_risk=metrics["mean_remaining_path_risk"],
            remaining_path_risk_var=metrics["remaining_path_risk_var"],
            cumulative_risk_exposure=metrics["cumulative_risk_exposure"],
            avg_path_cost=metrics["avg_path_cost"],
            avg_time=metrics["avg_time"],
            median_time=metrics["median_time"],
            p90_time=metrics["p90_time"],
            min_time=metrics["min_time"],
            max_time=metrics["max_time"],
        )

        upsert_experiment_metrics(
            simulation_conn,
            experiment_metrics,
        )


def run_single_mode(
    *,
    cfg: dict[str, Any],
    case_id: str,
    mode: int,
    paths: RunPaths,
    resources: ExperimentResources,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    congestion_reroute_epsilon: float = 0.1,
) -> None:
    log.info(
        "Mode start | mode=%s env=%s case=%s",
        mode,
        resources.env_name,
        cfg.get("name", "unknown"),
    )

    trajectory_file = paths.db_dir / f"{resources.env_name}_mode_{mode}.sqlite"

    simulation = create_simulation(
        walkable_area=resources.walkable_area,
        trajectory_file=trajectory_file,
        every_nth_frame_simulation=resources.every_nth_frame_simulation,
        strength_neighbor_repulsion=resources.jps_config.strength_neighbor_repulsion,
        range_neighbor_repulsion=resources.jps_config.range_neighbor_repulsion,
        range_geometry_repulsion=resources.jps_config.range_geometry_repulsion,
    )

    exit_ids, waypoints_ids = create_stages(
        simulation=simulation,
        targets=resources.targets,
        specific_areas=resources.specific_areas,
        waypoints=resources.waypoints,
    )

    agent_groups = build_agent_groups(
        simulation=simulation,
        mode=mode,
        mode_type=resources.mode_type,
        sources=resources.sources,
        targets=resources.targets,
        positions=resources.positions,
        exit_ids=exit_ids,
        waypoints_ids=waypoints_ids,
        env_info=resources.env_info,
        risk_first_frame=resources.risk_first_frame,
        gamma=resources.gamma,
        normal_max_speed=resources.normal_max_speed,
        heuristic=heuristic,
        beta=beta,
        horizon_k=horizon_k,
        grouping_config=resources.grouping_config,
        no_path_policy=resources.congestion_config.no_path_policy,
        logger=log,
    )

    sim_cfg = SimulationConfig(
        simulation=simulation,
        every_nth_frame_simulation=resources.every_nth_frame_simulation,
        every_nth_frame_animation=resources.every_nth_frame_animation,
        waypoints_ids=waypoints_ids,
        exit_ids=exit_ids,
        gamma=resources.gamma,
        normal_max_speed=resources.normal_max_speed,
        stairs_max_speed=resources.stairs_max_speed,
    )

    try:
        run_agent_simulation(
            sim_cfg,
            cfg.get("log_every_frames", 10),
            agent_groups,
            resources.env_info,
            resources.simulation_conn,
            case_name=case_id,
            mode=mode,
            threshold=resources.risk_threshold,
            heuristic=heuristic,
            beta=beta,
            horizon_k=horizon_k,
            congestion_reroute_epsilon=congestion_reroute_epsilon,
            group_split_threshold=cfg.get("group_split_threshold", None),
            no_path_policy=resources.congestion_config.no_path_policy,
        )
    except Exception:
        log.exception("Simulation failed | mode=%s", mode)
        raise

    del sim_cfg
    del simulation
    gc.collect()

    write_mode_results(
        case_id=case_id,
        mode=mode,
        graph=resources.graph,
        simulation_conn=resources.simulation_conn,
        trajectory_file=trajectory_file,
        risk_seed=resources.risk_seed,
        targets=resources.targets,
        sources=resources.sources,
        total_agents=resources.total_agents,
        agent_groups=agent_groups,
    )

    resources.simulation_conn.commit()

    generate_mode_visual_artifacts(
        trajectory_file=trajectory_file,
        walkable_area=resources.walkable_area,
        waypoints=resources.waypoints,
        target_nodes=resources.targets,
        specific_areas=resources.specific_areas,
        risk_db_file=resources.simulation_db_file,
        risk_threshold=resources.risk_threshold,
        case_name=case_id,
        danger_frame=resources.danger_visualization_frame,
        images_dir=paths.images_dir,
        env_name=resources.env_name,
        mode=mode,
    )

    log.info("Finished mode=%s", mode)


def export_final_results(
    *,
    simulation_db_file: Path,
    csv_dir: Path,
) -> None:
    experiments_csv = csv_dir / "experiments.csv"
    metrics_csv = csv_dir / "experiment_metrics.csv"

    export_experiments_to_csv(str(simulation_db_file), str(experiments_csv))
    export_experiment_metrics_to_csv(str(simulation_db_file), str(metrics_csv))

    log.info("Exported CSV: %s", experiments_csv)
    log.info("Exported CSV: %s", metrics_csv)


def run_experiment_from_case(
    cfg: dict[str, Any],
    paths: RunPaths,
    case_id: str,
    heuristic: str = "none",
    beta: float = 1.0,
    horizon_k: int | None = None,
    congestion_reroute_epsilon: float = 0.1,
    shared_simulation_conn: sqlite3.Connection | None = None,
    shared_simulation_db_file: Path | None = None,
) -> None:
    resources = prepare_shared_resources(
        cfg,
        paths,
        case_id,
        shared_simulation_conn,
        shared_simulation_db_file,
    )

    try:
        for mode in resources.modes:
            run_single_mode(
                cfg=cfg,
                case_id=case_id,
                mode=mode,
                paths=paths,
                resources=resources,
                heuristic=heuristic,
                beta=beta,
                horizon_k=horizon_k,
                congestion_reroute_epsilon=congestion_reroute_epsilon,
            )

        resources.simulation_conn.commit()

        if resources.owns_simulation_conn:
            export_final_results(
                simulation_db_file=resources.simulation_db_file,
                csv_dir=paths.csv_dir,
            )
    finally:
        if resources.owns_simulation_conn:
            resources.simulation_conn.close()