import json
import sqlite3
from typing import List

import pandas as pd


def create_group_path_table(connection: sqlite3.Connection, force_reset: bool = False) -> None:
    """
    Creates the 'group_path_data' table if it doesn't exist.
    If force_reset=True, drops and recreates the table.
    """
    try:
        with connection:
            if force_reset:
                connection.execute("DROP TABLE IF EXISTS group_path_data")

            connection.execute("""
                CREATE TABLE IF NOT EXISTS group_path_data (
                    frame INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    algorithm TEXT NOT NULL,
                    awareness TEXT NOT NULL,
                    current_area TEXT NOT NULL,
                    next_path TEXT NOT NULL,
                    est_risk_mean REAL NOT NULL,
                    est_risk_max REAL NOT NULL,
                    est_risk_min REAL NOT NULL,
                    est_risk_var REAL NOT NULL,
                    risk_now REAL NOT NULL,
                    PRIMARY KEY (frame, group_id, algorithm, awareness)
                )
                """)
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating group_path_data table: {e}")


def write_group_path_data(
    connection: sqlite3.Connection,
    frame: int,
    group_id: int,
    algorithm: str,
    awareness: str,
    current_area: str,
    next_path: List[str],
    est_risk_mean: float,
    est_risk_max: float,
    est_risk_min: float,
    est_risk_var: float,
    risk_now: float,
):
    """
    Inserts or replaces a record in group_path_data for the given frame, group, algorithm, and awareness.

    Note: To compute est_risk_* metrics, fetch static risk values for each area in next_path
          at the current frame (or use last known risk), then calculate mean, max, min, and variance.
    """
    try:
        with connection:
            path_str = json.dumps(next_path)
            connection.execute(
                """
                INSERT OR REPLACE INTO group_path_data (
                    frame, group_id, algorithm, awareness, current_area,
                    next_path, est_risk_mean, est_risk_max,
                    est_risk_min, est_risk_var, risk_now
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    frame,
                    group_id,
                    algorithm,
                    awareness,
                    current_area,
                    path_str,
                    est_risk_mean,
                    est_risk_max,
                    est_risk_min,
                    est_risk_var,
                    risk_now,
                ),
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error inserting group path data: {e}")


def read_group_path_data(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all records from group_path_data, parsing JSON paths back to lists.
    """
    try:
        df = pd.read_sql_query("SELECT * FROM group_path_data", connection)
        df["next_path"] = df["next_path"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading group path data: {e}")


def read_group_path_by_frame(connection: sqlite3.Connection, frame: int) -> pd.DataFrame:
    """
    Reads records for a specific simulation frame.
    """
    try:
        df = pd.read_sql_query(
            "SELECT * FROM group_path_data WHERE frame = ? AND algorithm = ? AND awareness = ?",
            connection,
            params=(frame,),
        )
        df["next_path"] = df["next_path"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading group path data for frame {frame}: {e}")
