import sqlite3
from collections import defaultdict
from typing import Any

import pandas as pd


def insert_risk_levels(
    connection: sqlite3.Connection,
    frame: int,
    risks: dict[str, float],
) -> None:
    try:
        with connection:
            rows = [(frame, area, risk) for area, risk in risks.items()]
            connection.executemany(
                "INSERT OR REPLACE INTO risk_data (frame, area, risk_level) VALUES (?, ?, ?)",
                rows,
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error saving risk levels: {e}")


def get_risk_levels_by_frame(
    connection: sqlite3.Connection,
    frame: int,
) -> dict[str, float]:
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT area, risk_level FROM risk_data WHERE frame = ? ORDER BY area",
            (frame,),
        )
        rows = cursor.fetchall()
        return {area: risk_level for area, risk_level in rows}
    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving risk levels for frame {frame}: {e}")


def get_all_risks(
    connection: sqlite3.Connection,
) -> list[tuple[int, str, float]]:
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT frame, area, risk_level FROM risk_data ORDER BY frame, area"
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        raise RuntimeError(f"Error fetching all risk data: {e}")


def get_risks_grouped_by_frame(
    connection: sqlite3.Connection,
) -> dict[int, dict[str, float]]:
    try:
        rows = get_all_risks(connection)
        grouped: dict[int, dict[str, float]] = defaultdict(dict)

        for frame, area, risk_level in rows:
            grouped[frame][area] = risk_level

        return dict(grouped)
    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving grouped risk data: {e}")


def get_risk_dataframe(connection: sqlite3.Connection) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT frame, area, risk_level FROM risk_data ORDER BY frame, area",
            connection,
        )
    except Exception as e:
        raise RuntimeError(f"Error reading risk data: {e}")


def get_high_risk_dataframe(
    connection: sqlite3.Connection,
    min_risk: float = 1.0,
) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT frame, area, risk_level FROM risk_data WHERE risk_level >= ? ORDER BY frame, area",
            connection,
            params=(min_risk,),
        )
    except Exception as e:
        raise RuntimeError(f"Error retrieving high risk data: {e}")