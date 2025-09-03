import sqlite3
import json
from typing import List, Dict, Any
import pandas as pd


def create_tables(connection: sqlite3.Connection):
    try:
        with connection:
            connection.execute("DROP TABLE IF EXISTS experiment_metrics")
            connection.execute("DROP TABLE IF EXISTS experiments")

            connection.execute(
                """
                CREATE TABLE experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    risk_nodes TEXT NOT NULL,
                    source_nodes TEXT NOT NULL,
                    agents_per_source TEXT NOT NULL,
                    random_seed INTEGER NOT NULL,
                    UNIQUE(
                        name,
                        risk_nodes,
                        source_nodes,
                        agents_per_source,
                        random_seed
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE experiment_metrics (
                    experiment_id INTEGER NOT NULL,
                    agent_group_id TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    awareness REAL NOT NULL,
                    n_records INTEGER,
                    mean_risk REAL,
                    mean_risk_var REAL,
                    avg_path_length REAL,
                    avg_time REAL,
                    max_time REAL,
                    PRIMARY KEY (experiment_id, agent_group_id, algorithm, awareness)
                    FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
                )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating tables: {e}")



def write_experiment(
    connection: sqlite3.Connection,
    name: str,
    risk_nodes: List[Any],
    source_nodes: List[Any],
    agents_per_source: Dict[Any, int],
    random_seed: int
) -> int:
    """
    Inserts or ignores a global experiment setup, returning its id.
    """
    try:
        with connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO experiments (
                    name,
                    risk_nodes,
                    source_nodes,
                    agents_per_source,
                    random_seed
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    name,
                    json.dumps(risk_nodes),
                    json.dumps(source_nodes),
                    json.dumps(agents_per_source),
                    random_seed
                )
            )
        cursor = connection.execute(
            "SELECT id FROM experiments WHERE name = ? AND risk_nodes = ? AND source_nodes = ? "
            "AND agents_per_source = ? AND random_seed = ?",
            (
                name,
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
    agent_group_id: str,
    algorithm: str,
    awareness: float,
    n_records: int,
    mean_risk: float,
    mean_risk_var: float,
    avg_path_length: float,
    avg_time: float,
    max_time: float
) :
    """
    Inserts or replaces metrics for a given experiment.
    """
    try:
        with connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO experiment_metrics (
                    experiment_id, agent_group_id, algorithm, awareness,
                    n_records, mean_risk, mean_risk_var,
                    avg_path_length, avg_time, max_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    agent_group_id,
                    algorithm,
                    awareness,
                    n_records,
                    mean_risk,
                    mean_risk_var,
                    avg_path_length,
                    avg_time,
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
            "SELECT m.*, e.name, e.risk_nodes, e.source_nodes, e.agents_per_source, e.random_seed "
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

def read_all_experiment_metrics(db_path: str) -> pd.DataFrame:
    """
    Lee todos los registros de experiment_metrics desde la base de datos.
    """
    conn = sqlite3.connect(db_path)

    try:
        df = pd.read_sql_query("SELECT * FROM experiment_metrics", conn)
        print("Métricas cargadas correctamente.")
        return df

    except Exception as e:
        raise RuntimeError(f"Error al leer experiment_metrics: {e}")
    finally:
        conn.close()

def export_experiments_to_csv(
        db_path: str,
        csv_path: str = "experiments.csv",
) -> str:
    """
    Exporta la tabla 'experiments' a un CSV.
    Devuelve la ruta del CSV generado.
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM experiments", conn)
        # Opcional: si prefieres legibilidad, puedes dejar los JSON como están (strings).
        # Si quisieras expandirlos, podrías hacer json.loads() y luego normalizar.
        df.to_csv(csv_path, index=False)
        return csv_path
    except Exception as e:
        raise RuntimeError(f"Error exportando experiments a CSV: {e}")
    finally:
        conn.close()

def export_experiment_metrics_to_csv(
        db_path: str,
        csv_path: str = "experiment_metrics.csv",
        include_experiment_context: bool = True,
        convert_agent_group_id_bytes: bool = True,
) -> str:
    """
    Exporta 'experiment_metrics' a CSV.
    - include_experiment_context=True añade columnas de 'experiments' (name, risk_nodes, etc.) mediante JOIN.
    - convert_agent_group_id_bytes=True convierte agent_group_id de bytes a entero si viniera en binario.
    Devuelve la ruta del CSV generado.
    """
    conn = sqlite3.connect(db_path)
    try:
        if include_experiment_context:
            query = (
                "SELECT m.*, e.name, e.risk_nodes, e.source_nodes, e.agents_per_source, e.random_seed "
                "FROM experiment_metrics m "
                "JOIN experiments e ON m.experiment_id = e.id"
            )
        else:
            query = "SELECT * FROM experiment_metrics"

        df = pd.read_sql_query(query, conn)

        # Conversión opcional de agent_group_id binario -> entero legible
        if convert_agent_group_id_bytes and "agent_group_id" in df.columns:
            def _conv(v):
                if isinstance(v, (bytes, bytearray)):
                    return int.from_bytes(v, byteorder="little")
                return v

            df["agent_group_id"] = df["agent_group_id"].apply(_conv)

        # Nota: dejamos risk/source/agents_per_source como JSON strings para mantener estructura en CSV.
        # Si quisieras, podríamos json.loads() y normalizar, pero se perdería estructura en columnas planas.

        df.to_csv(csv_path, index=False)
        return csv_path
    except Exception as e:
        raise RuntimeError(f"Error exportando experiment_metrics a CSV: {e}")
    finally:
        conn.close()
