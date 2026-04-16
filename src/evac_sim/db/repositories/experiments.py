import json
import sqlite3
import pandas as pd
from typing import Any
from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class ExperimentConfig:
    case_name: str
    risk_nodes: list[Any]
    source_nodes: list[Any]
    agents_per_source: list[int]
    random_seed: int


@dataclass(slots=True, frozen=True)
class ExperimentMetrics:
    experiment_id: int
    agent_group_id: str
    algorithm: str
    awareness: float
    n_records: int
    mean_remaining_path_risk: float
    remaining_path_risk_var: float
    cumulative_risk_exposure: float
    avg_path_cost: float
    min_time: float
    avg_time: float
    median_time: float
    p90_time: float
    max_time: float

def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _from_json(value: str) -> Any:
    return json.loads(value)

def upsert_experiment(
    connection: sqlite3.Connection,
    config: ExperimentConfig,
) -> int:
    try:
        risk_json = _to_json(config.risk_nodes)
        source_json = _to_json(config.source_nodes)
        agents_json = _to_json(config.agents_per_source)

        with connection:
            row = connection.execute(
                """
                SELECT id, risk_nodes, source_nodes, agents_per_source, random_seed
                FROM experiments
                WHERE case_name = ?
                """,
                (config.case_name,),
            ).fetchone()

            if row is not None:
                experiment_id, ex_risk, ex_source, ex_agents, ex_seed = row
                same_config = (
                    ex_risk == risk_json
                    and ex_source == source_json
                    and ex_agents == agents_json
                    and ex_seed == config.random_seed
                )

                if same_config:
                    return experiment_id

                connection.execute(
                    "DELETE FROM experiments WHERE id = ?",
                    (experiment_id,),
                )

            connection.execute(
                """
                INSERT INTO experiments (
                    case_name, risk_nodes, source_nodes, agents_per_source, random_seed
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    config.case_name,
                    risk_json,
                    source_json,
                    agents_json,
                    config.random_seed,
                ),
            )

            return connection.execute(
                "SELECT id FROM experiments WHERE case_name = ?",
                (config.case_name,),
            ).fetchone()[0]
    except sqlite3.Error as e:
        raise RuntimeError(f"Error upserting experiment: {e}")

def upsert_experiment_metrics(
    connection: sqlite3.Connection,
    metrics: ExperimentMetrics,
) -> None:
    try:
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO experiment_metrics (
                    experiment_id,
                    agent_group_id,
                    algorithm,
                    awareness,
                    n_records,
                    mean_remaining_path_risk,
                    remaining_path_risk_var,
                    cumulative_risk_exposure,
                    avg_path_cost,
                    min_time,
                    avg_time,
                    median_time,
                    p90_time,
                    max_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics.experiment_id,
                    metrics.agent_group_id,
                    metrics.algorithm,
                    metrics.awareness,
                    metrics.n_records,
                    metrics.mean_remaining_path_risk,
                    metrics.remaining_path_risk_var,
                    metrics.cumulative_risk_exposure,
                    metrics.avg_path_cost,
                    metrics.min_time,
                    metrics.avg_time,
                    metrics.median_time,
                    metrics.p90_time,
                    metrics.max_time,
                ),
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error upserting experiment metrics: {e}")

def get_all_experiments(connection: sqlite3.Connection) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(
            "SELECT * FROM experiments ORDER BY id",
            connection,
        )
        if not df.empty:
            df["risk_nodes"] = df["risk_nodes"].apply(_from_json)
            df["source_nodes"] = df["source_nodes"].apply(_from_json)
            df["agents_per_source"] = df["agents_per_source"].apply(_from_json)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading experiments: {e}")


def get_all_experiment_metrics(
    connection: sqlite3.Connection,
    include_experiment_context: bool = True,
) -> pd.DataFrame:
    try:
        if include_experiment_context:
            query = """
                SELECT
                    m.*,
                    e.case_name,
                    e.risk_nodes,
                    e.source_nodes,
                    e.agents_per_source,
                    e.random_seed
                FROM experiment_metrics m
                JOIN experiments e ON m.experiment_id = e.id
                ORDER BY m.experiment_id, m.agent_group_id, m.algorithm, m.awareness
            """
        else:
            query = """
                SELECT *
                FROM experiment_metrics
                ORDER BY experiment_id, agent_group_id, algorithm, awareness
            """

        df = pd.read_sql_query(query, connection)

        if include_experiment_context and not df.empty:
            df["risk_nodes"] = df["risk_nodes"].apply(_from_json)
            df["source_nodes"] = df["source_nodes"].apply(_from_json)
            df["agents_per_source"] = df["agents_per_source"].apply(_from_json)

        return df
    except Exception as e:
        raise RuntimeError(f"Error reading experiment metrics: {e}")

def find_experiment_id(
    connection: sqlite3.Connection,
    config: ExperimentConfig,
) -> int | None:
    try:
        risk_json = _to_json(config.risk_nodes)
        source_json = _to_json(config.source_nodes)
        agents_json = _to_json(config.agents_per_source)

        row = connection.execute(
            """
            SELECT id
            FROM experiments
            WHERE case_name = ?
              AND risk_nodes = ?
              AND source_nodes = ?
              AND agents_per_source = ?
              AND random_seed = ?
            """,
            (
                config.case_name,
                risk_json,
                source_json,
                agents_json,
                config.random_seed,
            ),
        ).fetchone()

        return None if row is None else row[0]
    except sqlite3.Error as e:
        raise RuntimeError(f"Error finding experiment: {e}")


def get_metrics_for_experiment(
    connection: sqlite3.Connection,
    experiment_id: int,
) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            """
            SELECT *
            FROM experiment_metrics
            WHERE experiment_id = ?
            ORDER BY agent_group_id, algorithm, awareness
            """,
            connection,
            params=(experiment_id,),
        )
    except Exception as e:
        raise RuntimeError(f"Error reading metrics for experiment {experiment_id}: {e}")