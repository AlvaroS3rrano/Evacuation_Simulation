import sqlite3
from collections import defaultdict
import pandas as pd
def create_risk_table(connection: sqlite3.Connection):
    """
    Creates a table to store risk levels in the SQLite database.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.

    Raises:
        RuntimeError: If there is an error creating the table.
    """
    try:
        with connection:
            connection.execute("DROP TABLE IF EXISTS risk_data")
            connection.execute(
                """
                CREATE TABLE risk_data (
                    frame INTEGER NOT NULL,
                    area TEXT NOT NULL,
                    risk_level REAL NOT NULL,
                    floor INTEGER NOT NULL,
                    PRIMARY KEY (frame, area)
                )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating risk_data table: {e}")


def write_risk_levels(connection: sqlite3.Connection, frame: int, risks: dict):
    """
    Stores risk levels in the database for a specific frame.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.
        frame (int): Frame number.
        risks (dict): Dictionary where keys are areas and values are risk levels.

    Raises:
        RuntimeError: If there is an error saving the risk levels.
    """
    try:
        with connection:
            risk_data = [
                (frame, area, value["risk"], value["floor"])
                for area, value in risks.items()
            ]
            connection.executemany(
                "INSERT OR REPLACE INTO risk_data (frame, area, risk_level, floor) VALUES (?, ?, ?, ?)",
                risk_data,
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error saving risk levels: {e}")


def read_risk_data(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all risk data stored in the database.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.

    Returns:
        pd.DataFrame: A DataFrame containing all risk data.

    Raises:
        RuntimeError: If there is an error reading the data.
    """
    try:
        query = "SELECT * FROM risk_data"
        return pd.read_sql_query(query, connection)
    except Exception as e:
        raise RuntimeError(f"Error reading risk data: {e}")


def get_risk_levels_by_frame(connection: sqlite3.Connection, frame: int) -> dict:
    """
    Retrieves a dictionary mapping areas to their risk levels for a specific frame.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.
        frame (int): Frame number to query.

    Returns:
        dict: {area: risk_level}

    Raises:
        RuntimeError: If there is an error fetching data.
    """
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT area, risk_level FROM risk_data WHERE frame = ?", (frame,))
        rows = cursor.fetchall()
        return {area: risk_level for area, risk_level in rows}
    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving risk levels for frame {frame}: {e}")


def get_risks_grouped_by_frame_and_floor(connection: sqlite3.Connection) -> dict:
    """
    Retrieves a nested dictionary where each floor maps to a dictionary where each frame maps to
    a dictionary of areas and risk levels.

    The returned dictionary has the following structure:
        {
            floor: {
                frame: { area: risk_level, ... },
                ...
            },
            ...
        }

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.

    Returns:
        dict: Nested dictionary with risk data grouped by floor and frame.

    Raises:
        RuntimeError: If there is an error fetching data.
    """
    try:
        # Ensure we select the floor column along with frame, area, and risk_level.
        query = "SELECT frame, area, risk_level, floor FROM risk_data ORDER BY floor, frame, area"
        cursor = connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()

        # Group the results into a nested dictionary: floor -> frame -> {area: risk_level}
        risks_per_floor = defaultdict(lambda: defaultdict(dict))
        for frame, area, risk_level, floor in results:
            risks_per_floor[floor][frame][area] = risk_level

        # Convert nested defaultdicts to regular dicts before returning.
        return {floor: dict(frames) for floor, frames in risks_per_floor.items()}
    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving grouped risk data: {e}")


def fetch_all_risks(connection: sqlite3.Connection) -> list:
    """
    Fetches all risk data from the database.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.

    Returns:
        list of tuple: A list of tuples containing (frame, area, risk_level).

    Raises:
        RuntimeError: If there is an error fetching data.
    """
    try:
        query = "SELECT frame, area, risk_level FROM risk_data ORDER BY frame, area"
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall()
    except sqlite3.Error as e:
        raise RuntimeError(f"Error fetching all risk data: {e}")



