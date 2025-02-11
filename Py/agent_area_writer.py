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

def write_agent_area(connection: sqlite3.Connection, frame: int, agents: List[int], area: str, risk: float):
    """
    Stores the area assignment for a list of agents in a specific frame into the database, including risk levels.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        frame (int): The frame number to which the assignments correspond.
        agents (List[int]): A list of agent IDs (integers) that are assigned to the specified area.
        area (str): The name of the area to which the agents are assigned.
        risk (float): The risk level associated with the area.

    Raises:
        RuntimeError: If there is an error while inserting the data into the database.
    """
    try:
        with connection:
            data = [(frame, agent_id, area, risk) for agent_id in agents]
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
