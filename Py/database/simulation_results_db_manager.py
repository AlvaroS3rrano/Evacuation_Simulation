import sqlite3
import json
from typing import List, Dict, Any
import pandas as pd


def create_tables(connection: sqlite3.Connection):
    """
    Creates two tables:
      - experiments: stores unique simulation parameter sets (algorithm, awareness, risk_nodes, source_nodes, agents_per_source, random_seed)
      - experiment_metrics: stores result metrics linked to experiments
    """
    try:
        with connection:
            # Drop existing tables
            connection.execute("DROP TABLE IF EXISTS experiment_metrics")
            connection.execute("DROP TABLE IF EXISTS experiments")

            # Experiments table: global parameters
            connection.execute(
                """
                CREATE TABLE experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    algorithm TEXT NOT NULL,
                    awareness REAL NOT NULL,
                    risk_nodes TEXT NOT NULL,
                    source_nodes TEXT NOT NULL,
                    agents_per_source TEXT NOT NULL,
                    random_seed INTEGER NOT NULL,
                    UNIQUE(
                        algorithm,
                        awareness,
                        risk_nodes,
                        source_nodes,
                        agents_per_source,
                        random_seed
                    )
                )
                """
            )

            # Metrics table: per experiment
            connection.execute(
                """
                CREATE TABLE experiment_metrics (
                    experiment_id INTEGER PRIMARY KEY,
                    n_records INTEGER,
                    mean_risk REAL,
                    mean_risk_var REAL,
                    avg_path_length REAL,
                    max_time REAL,
                    FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
                )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating tables: {e}")


def write_experiment(
    connection: sqlite3.Connection,
    algorithm: str,
    awareness: float,
    risk_nodes: List[Any],
    source_nodes: List[Any],
    agents_per_source: Dict[Any, int],
    random_seed: int
) -> int:
    """
    Inserts or ignores an experiment parameter set, returning its id.
    """
    try:
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO experiments (
                    algorithm, awareness, risk_nodes,
                    source_nodes, agents_per_source,
                    random_seed
                ) VALUES (?, ?, ?, ?, ?, ?)""" ,
                (
                    algorithm,
                    awareness,
                    json.dumps(risk_nodes),
                    json.dumps(source_nodes),
                    json.dumps(agents_per_source),
                    random_seed
                )
            )
        cursor = connection.execute(
            "SELECT id FROM experiments WHERE algorithm = ? AND awareness = ? "
            "AND risk_nodes = ? AND source_nodes = ? "
            "AND agents_per_source = ? AND random_seed = ?",
            (
                algorithm,
                awareness,
                json.dumps(risk_nodes),
                json.dumps(source_nodes),
                json.dumps(agents_per_source),
                random_seed
            )
        )
        row = cursor.fetchone()
        return row[0]
    except sqlite3.Error as e:
        raise RuntimeError(f"Error writing experiment: {e}")


def write_experiment_metrics(
    connection: sqlite3.Connection,
    experiment_id: int,
    n_records: int,
    mean_risk: float,
    mean_risk_var: float,
    avg_path_length: float,
    max_time: float
):
    """
    Inserts or replaces metrics for a given experiment.
    """
    try:
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO experiment_metrics (
                    experiment_id, n_records,
                    mean_risk, mean_risk_var,
                    avg_path_length, max_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    n_records,
                    mean_risk,
                    mean_risk_var,
                    avg_path_length,
                    max_time
                )
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error writing experiment metrics: {e}")


def read_all_experiments(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all experiments into a DataFrame, decoding JSON fields.
    """
    try:
        df = pd.read_sql_query("SELECT * FROM experiments", connection)
        df["risk_nodes"] = df["risk_nodes"].apply(json.loads)
        df["source_nodes"] = df["source_nodes"].apply(json.loads)
        df["agents_per_source"] = df["agents_per_source"].apply(lambda s: json.loads(s))
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading experiments: {e}")


def read_all_metrics(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all metrics, joining with experiments for context.
    """
    try:
        query = (
            "SELECT m.experiment_id, e.algorithm, e.awareness, e.risk_nodes, "
            "e.source_nodes, e.agents_per_source, e.random_seed, "
            "m.n_records, m.mean_risk, m.mean_risk_var, "
            "m.avg_path_length, m.max_time "
            "FROM experiment_metrics m "
            "JOIN experiments e ON m.experiment_id = e.id"
        )
        df = pd.read_sql_query(query, connection)
        df["risk_nodes"] = df["risk_nodes"].apply(json.loads)
        df["source_nodes"] = df["source_nodes"].apply(json.loads)
        df["agents_per_source"] = df["agents_per_source"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading experiment metrics: {e}")


def read_metrics_by_experiment(
    connection: sqlite3.Connection,
    algorithm: str,
    awareness: float,
    risk_nodes: List[Any],
    source_nodes: List[Any],
    agents_per_source: Dict[Any, int],
    random_seed: int
) -> pd.DataFrame:
    """
    Retrieves metrics for the specified experiment parameters.
    """
    try:
        exp_id = write_experiment(
            connection,
            algorithm,
            awareness,
            risk_nodes,
            source_nodes,
            agents_per_source,
            random_seed
        )
        query = "SELECT * FROM experiment_metrics WHERE experiment_id = ?"
        df = pd.read_sql_query(query, connection, params=(exp_id,))
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading metrics for experiment: {e}")
