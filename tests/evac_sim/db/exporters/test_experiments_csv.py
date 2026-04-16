import sqlite3
from pathlib import Path

import pandas as pd

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
from evac_sim.db.schema import create_experiments_tables


def test_export_experiments_to_csv(tmp_path: Path):
    db_path = tmp_path / "test.db"
    csv_path = tmp_path / "experiments.csv"

    conn = sqlite3.connect(db_path)
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A", "B"],
        source_nodes=["S1"],
        agents_per_source=[10, 20],
        random_seed=42,
    )
    upsert_experiment(conn, config)
    conn.close()

    output_path = export_experiments_to_csv(str(db_path), str(csv_path))

    assert output_path == str(csv_path)
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert df.iloc[0]["case_name"] == "case_1"


def test_export_experiment_metrics_to_csv_with_context(tmp_path: Path):
    db_path = tmp_path / "test.db"
    csv_path = tmp_path / "experiment_metrics.csv"

    conn = sqlite3.connect(db_path)
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )
    experiment_id = upsert_experiment(conn, config)

    metrics = ExperimentMetrics(
        experiment_id=experiment_id,
        agent_group_id="g1",
        algorithm="shortest",
        awareness=1.0,
        n_records=5,
        mean_remaining_path_risk=0.2,
        remaining_path_risk_var=0.01,
        cumulative_risk_exposure=0.4,
        avg_path_cost=12.0,
        min_time=10.0,
        avg_time=12.0,
        median_time=11.5,
        p90_time=14.0,
        max_time=15.0,
    )
    upsert_experiment_metrics(conn, metrics)
    conn.close()

    output_path = export_experiment_metrics_to_csv(
        str(db_path),
        str(csv_path),
        include_experiment_context=True,
    )

    assert output_path == str(csv_path)
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert "case_name" in df.columns
    assert "risk_nodes" in df.columns
    assert df.iloc[0]["case_name"] == "case_1"


def test_export_experiment_metrics_to_csv_without_context(tmp_path: Path):
    db_path = tmp_path / "test.db"
    csv_path = tmp_path / "experiment_metrics.csv"

    conn = sqlite3.connect(db_path)
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )
    experiment_id = upsert_experiment(conn, config)

    metrics = ExperimentMetrics(
        experiment_id=experiment_id,
        agent_group_id="g1",
        algorithm="shortest",
        awareness=0.0,
        n_records=3,
        mean_remaining_path_risk=0.1,
        remaining_path_risk_var=0.01,
        cumulative_risk_exposure=0.2,
        avg_path_cost=8.0,
        min_time=7.0,
        avg_time=8.0,
        median_time=8.0,
        p90_time=9.0,
        max_time=10.0,
    )
    upsert_experiment_metrics(conn, metrics)
    conn.close()

    output_path = export_experiment_metrics_to_csv(
        str(db_path),
        str(csv_path),
        include_experiment_context=False,
    )

    assert output_path == str(csv_path)
    assert csv_path.exists()

    df = pd.read_csv(csv_path)
    assert len(df) == 1
    assert "case_name" not in df.columns
    assert "risk_nodes" not in df.columns