import sqlite3

from evac_sim.db.repositories.experiments import (
    ExperimentConfig,
    ExperimentMetrics,
    find_experiment_id,
    get_all_experiment_metrics,
    get_all_experiments,
    get_metrics_for_experiment,
    upsert_experiment,
    upsert_experiment_metrics,
)
from evac_sim.db.schema import create_experiments_tables


def test_upsert_experiment_inserts_new_experiment():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A", "B"],
        source_nodes=["S1", "S2"],
        agents_per_source=[10, 20],
        random_seed=42,
    )

    experiment_id = upsert_experiment(conn, config)

    assert isinstance(experiment_id, int)
    assert experiment_id > 0

    rows = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    assert rows == 1


def test_upsert_experiment_reuses_existing_id_for_same_config():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )

    exp_id_1 = upsert_experiment(conn, config)
    exp_id_2 = upsert_experiment(conn, config)

    assert exp_id_1 == exp_id_2

    rows = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
    assert rows == 1


def test_upsert_experiment_replaces_existing_case_when_config_changes():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config_1 = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )
    config_2 = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A", "B"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )

    exp_id_1 = upsert_experiment(conn, config_1)
    exp_id_2 = upsert_experiment(conn, config_2)

    rows = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]

    assert rows == 1
    assert isinstance(exp_id_2, int)
    assert exp_id_2 > 0
    assert find_experiment_id(conn, config_1) is None
    assert find_experiment_id(conn, config_2) == exp_id_2


def test_get_all_experiments_decodes_json_columns():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A", "B"],
        source_nodes=["S1"],
        agents_per_source=[10, 15],
        random_seed=7,
    )
    upsert_experiment(conn, config)

    df = get_all_experiments(conn)

    assert len(df) == 1
    assert df.iloc[0]["case_name"] == "case_1"
    assert df.iloc[0]["risk_nodes"] == ["A", "B"]
    assert df.iloc[0]["source_nodes"] == ["S1"]
    assert df.iloc[0]["agents_per_source"] == [10, 15]
    assert df.iloc[0]["random_seed"] == 7


def test_find_experiment_id_returns_existing_id():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["R1"],
        source_nodes=["S1"],
        agents_per_source=[5],
        random_seed=99,
    )

    experiment_id = upsert_experiment(conn, config)
    found_id = find_experiment_id(conn, config)

    assert found_id == experiment_id


def test_find_experiment_id_returns_none_for_unknown_config():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["R1"],
        source_nodes=["S1"],
        agents_per_source=[5],
        random_seed=99,
    )

    assert find_experiment_id(conn, config) is None


def test_upsert_experiment_metrics_and_get_metrics_for_experiment():
    conn = sqlite3.connect(":memory:")
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

    df = get_metrics_for_experiment(conn, experiment_id)

    assert len(df) == 1
    assert df.iloc[0]["experiment_id"] == experiment_id
    assert df.iloc[0]["agent_group_id"] == "g1"
    assert df.iloc[0]["algorithm"] == "shortest"
    assert df.iloc[0]["avg_time"] == 12.0


def test_upsert_experiment_metrics_replaces_existing_row():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A"],
        source_nodes=["S1"],
        agents_per_source=[10],
        random_seed=42,
    )
    experiment_id = upsert_experiment(conn, config)

    metrics_1 = ExperimentMetrics(
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
    metrics_2 = ExperimentMetrics(
        experiment_id=experiment_id,
        agent_group_id="g1",
        algorithm="shortest",
        awareness=1.0,
        n_records=7,
        mean_remaining_path_risk=0.3,
        remaining_path_risk_var=0.02,
        cumulative_risk_exposure=0.5,
        avg_path_cost=13.0,
        min_time=11.0,
        avg_time=13.0,
        median_time=12.5,
        p90_time=15.0,
        max_time=16.0,
    )

    upsert_experiment_metrics(conn, metrics_1)
    upsert_experiment_metrics(conn, metrics_2)

    df = get_metrics_for_experiment(conn, experiment_id)

    assert len(df) == 1
    assert df.iloc[0]["n_records"] == 7
    assert df.iloc[0]["mean_remaining_path_risk"] == 0.3
    assert df.iloc[0]["avg_path_cost"] == 13.0


def test_get_all_experiment_metrics_with_context_decodes_json_columns():
    conn = sqlite3.connect(":memory:")
    create_experiments_tables(conn)

    config = ExperimentConfig(
        case_name="case_1",
        risk_nodes=["A", "B"],
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

    df = get_all_experiment_metrics(conn, include_experiment_context=True)

    assert len(df) == 1
    assert df.iloc[0]["case_name"] == "case_1"
    assert df.iloc[0]["risk_nodes"] == ["A", "B"]
    assert df.iloc[0]["source_nodes"] == ["S1"]
    assert df.iloc[0]["agents_per_source"] == [10]


def test_get_all_experiment_metrics_without_context():
    conn = sqlite3.connect(":memory:")
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
        n_records=2,
        mean_remaining_path_risk=0.2,
        remaining_path_risk_var=0.01,
        cumulative_risk_exposure=0.3,
        avg_path_cost=10.0,
        min_time=9.0,
        avg_time=10.0,
        median_time=10.0,
        p90_time=11.0,
        max_time=12.0,
    )
    upsert_experiment_metrics(conn, metrics)

    df = get_all_experiment_metrics(conn, include_experiment_context=False)

    assert len(df) == 1
    assert "case_name" not in df.columns
    assert "risk_nodes" not in df.columns