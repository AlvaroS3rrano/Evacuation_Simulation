import sqlite3
import pandas as pd
from typing import List
import math

def create_agent_area_table(connection: sqlite3.Connection):
    """
    Creates a table to store the relationship between frames, agent IDs, areas, and risk levels in the SQLite database.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Raises:
        RuntimeError: If there is an error creating the table.
    """
    try:
        with connection:
            connection.execute("DROP TABLE IF EXISTS agent_area_data")  # Elimina la tabla si ya existe
            connection.execute(
                """
                CREATE TABLE agent_area_data (
                    frame INTEGER NOT NULL,
                    agent_id INTEGER NOT NULL,
                    area TEXT NOT NULL,
                    risk FLOAT NOT NULL,
                    PRIMARY KEY (frame, agent_id)
                )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating agent_area_data table: {e}")

def write_agent_area(connection: sqlite3.Connection, frame: int, agents: List[int], areas: dict, risk_this_frame: dict):
    """
    Stores the area assignment for a list of agents in a specific frame into the database, including risk levels.
    Each agent's area is determined from the provided 'areas' dictionary, and the risk is obtained from the
    'risk_this_frame' dictionary using the area as the key.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        frame (int): The frame number to which the assignments correspond.
        agents (List[int]): A list of agent IDs (integers) that are assigned to an area.
        areas (dict): A dictionary mapping each agent ID to the area (e.g., current node) to which the agent is assigned.
        risk_this_frame (dict): A dictionary mapping each area (str) to its risk value (float).

    Raises:
        RuntimeError: If there is an error while inserting the data into the database.
    """
    try:
        with connection:
            data = []
            for agent_id in agents:
                area = areas.get(agent_id, "")
                # Get the risk for the area, defaulting to 0.0 if not found
                risk = risk_this_frame.get(area, 0.0)
                data.append((frame, agent_id, area, risk))
            connection.executemany(
                "INSERT OR REPLACE INTO agent_area_data (frame, agent_id, area, risk) VALUES (?, ?, ?, ?)",
                data,
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error saving agent area data: {e}")


def read_agent_area_data(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all the data stored in the agent_area_data table.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        pd.DataFrame: A DataFrame containing all the columns: frame, agent_id, and area.

    Raises:
        RuntimeError: If there is an error reading the data.
    """
    try:
        query = "SELECT * FROM agent_area_data"
        return pd.read_sql_query(query, connection)
    except Exception as e:
        raise RuntimeError(f"Error reading agent area data: {e}")

def read_agent_area_data_by_frame(connection: sqlite3.Connection, frame: int) -> pd.DataFrame:
    """
    Reads the data stored in the agent_area_data table for a specified frame.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        frame (int): The frame number to filter the data by.

    Returns:
        pd.DataFrame: A DataFrame containing all columns for the rows where frame equals the provided value.

    Raises:
        RuntimeError: If there is an error reading the data.
    """
    try:
        query = "SELECT * FROM agent_area_data WHERE frame = ?"
        return pd.read_sql_query(query, connection, params=(frame,))
    except Exception as e:
        raise RuntimeError(f"Error reading agent area data for frame {frame}: {e}")

def get_total_risk(connection: sqlite3.Connection) -> float:
    """
    Calculates the total risk level across all agents and frames in the simulation,
    rounding the result up to one decimal place.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        float: The overall total risk level in the simulation, rounded up to 1 decimal place.

    Raises:
        RuntimeError: If there is an error retrieving the data.
    """
    try:
        query = "SELECT SUM(risk) AS total_risk FROM agent_area_data;"
        cursor = connection.cursor()
        cursor.execute(query)
        result = cursor.fetchone()

        if result and result[0] is not None:
            # Round up to one decimal place
            return math.ceil(result[0] * 10) / 10
        return 0.0  # Return 0.0 if there is no data

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving total risk: {e}")

def get_max_risk(connection: sqlite3.Connection) -> float:
    """
    Calculates the highest risk level among all agents and frames in the simulation,
    rounding the result up to one decimal place.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        float: The highest risk level in the simulation, rounded up to 1 decimal place.

    Raises:
        RuntimeError: If there is an error retrieving the data.
    """
    try:
        query = "SELECT MAX(risk) AS max_risk FROM agent_area_data;"
        cursor = connection.cursor()
        cursor.execute(query)
        result = cursor.fetchone()

        if result and result[0] is not None:
            # Round up to one decimal place
            return math.ceil(result[0] * 10) / 10
        return 0.0  # Return 0.0 if there is no data

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving maximum risk: {e}")

def get_average_risk(connection: sqlite3.Connection) -> float:
    """
    Calculates the average risk level across all agents and frames in the simulation,
    rounding the result up to one decimal place.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        float: The overall average risk level in the simulation, rounded up to 1 decimal place.

    Raises:
        RuntimeError: If there is an error retrieving the data.
    """
    try:
        query = "SELECT AVG(risk) AS avg_risk_level FROM agent_area_data;"
        cursor = connection.cursor()
        cursor.execute(query)
        result = cursor.fetchone()

        if result and result[0] is not None:
            # Round up to one decimal place
            return math.ceil(result[0] * 10) / 10
        return 0.0  # Return 0.0 if there is no data

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving average risk: {e}")
