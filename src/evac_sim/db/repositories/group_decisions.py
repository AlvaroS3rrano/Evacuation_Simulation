import json
import sqlite3
from typing import Any
import pandas as pd


def insert_group_decision(
    connection: sqlite3.Connection,
    case_name: str,
    mode: int,
    frame: int,
    group_id: str,
    algorithm: str,
    awareness: str,
    current_area: str,
    next_path: list[str],
    est_risk_mean: float,
    est_risk_max: float,
    est_risk_min: float,
    est_risk_var: float,
    risk_now: float,
) -> None:
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO group_path_data (
                case_name, mode, frame, group_id, algorithm, awareness,
                current_area, next_path, est_risk_mean, est_risk_max,
                est_risk_min, est_risk_var, risk_now
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_name,
                mode,
                frame,
                group_id,
                algorithm,
                awareness,
                current_area,
                json.dumps(next_path),
                est_risk_mean,
                est_risk_max,
                est_risk_min,
                est_risk_var,
                risk_now,
            ),
        )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error inserting group decision data: {e}")


def get_group_decisions_dataframe(
    connection: sqlite3.Connection,
    case_name: str,
    mode: int,
) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM group_path_data
            WHERE case_name = ? AND mode = ?
            ORDER BY frame, group_id
            """,
            connection,
            params=(case_name, mode),
        )
        if not df.empty:
            df["next_path"] = df["next_path"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading group decision data: {e}")