import sqlite3
from collections import defaultdict
import pandas as pd


def insert_risk_levels(
    connection: sqlite3.Connection,
    case_name: str,
    frame: int,
    risks: dict[str, float],
) -> None:
    try:
        rows = [(case_name, frame, area, risk) for area, risk in risks.items()]
        connection.executemany(
            """
            INSERT OR REPLACE INTO risk_data (case_name, frame, area, risk_level)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error saving risk levels: {e}")


def get_risk_levels_by_frame(
    connection: sqlite3.Connection,
    case_name: str,
    frame: int,
) -> dict[str, float]:
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT area, risk_level
            FROM risk_data
            WHERE case_name = ? AND frame = ?
            ORDER BY area
            """,
            (case_name, frame),
        )
        rows = cursor.fetchall()
        return {area: risk_level for area, risk_level in rows}
    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving risk levels for frame {frame}: {e}")


def get_risk_dataframe(connection: sqlite3.Connection, case_name: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            """
            SELECT frame, area, risk_level
            FROM risk_data
            WHERE case_name = ?
            ORDER BY frame, area
            """,
            connection,
            params=(case_name,),
        )
    except Exception as e:
        raise RuntimeError(f"Error reading risk data: {e}")