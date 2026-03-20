import json
import sqlite3
from typing import Any

import pandas as pd


def insert_group_decision(
    connection: sqlite3.Connection,
    frame: int,
    group_id: int,
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
        with connection:
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


def get_group_decisions_dataframe(connection: sqlite3.Connection) -> pd.DataFrame:
    try:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM group_path_data
            ORDER BY frame, group_id, algorithm, awareness
            """,
            connection,
        )
        if not df.empty:
            df["next_path"] = df["next_path"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading group decision data: {e}")


def get_group_decisions_by_frame(
    connection: sqlite3.Connection,
    frame: int,
    algorithm: str | None = None,
    awareness: str | None = None,
) -> pd.DataFrame:
    try:
        query = """
            SELECT *
            FROM group_path_data
            WHERE frame = ?
        """
        params: list[Any] = [frame]

        if algorithm is not None:
            query += " AND algorithm = ?"
            params.append(algorithm)

        if awareness is not None:
            query += " AND awareness = ?"
            params.append(awareness)

        query += " ORDER BY group_id, algorithm, awareness"

        df = pd.read_sql_query(query, connection, params=tuple(params))
        if not df.empty:
            df["next_path"] = df["next_path"].apply(json.loads)
        return df
    except Exception as e:
        raise RuntimeError(f"Error reading group decision data for frame {frame}: {e}")


def get_group_decision(
    connection: sqlite3.Connection,
    frame: int,
    group_id: int,
    algorithm: str,
    awareness: str,
) -> dict[str, Any] | None:
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            """
            SELECT frame, group_id, algorithm, awareness, current_area, next_path,
                   est_risk_mean, est_risk_max, est_risk_min, est_risk_var, risk_now
            FROM group_path_data
            WHERE frame = ? AND group_id = ? AND algorithm = ? AND awareness = ?
            """,
            (frame, group_id, algorithm, awareness),
        ).fetchone()

        if row is None:
            return None

        return {
            "frame": row[0],
            "group_id": row[1],
            "algorithm": row[2],
            "awareness": row[3],
            "current_area": row[4],
            "next_path": json.loads(row[5]),
            "est_risk_mean": row[6],
            "est_risk_max": row[7],
            "est_risk_min": row[8],
            "est_risk_var": row[9],
            "risk_now": row[10],
        }
    except sqlite3.Error as e:
        raise RuntimeError(
            f"Error reading group decision for frame={frame}, group_id={group_id}: {e}"
        )