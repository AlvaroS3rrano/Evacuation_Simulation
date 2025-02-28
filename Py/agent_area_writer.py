import sqlite3
import pandas as pd
from typing import List
import math
from collections import defaultdict

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

# not used
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


def calculate_average_agent_combined_risk(connection: sqlite3.Connection) -> float:
    """
    Calculates the combined risk for each agent in the simulation and returns the average of these risks.

    In the 'agent_area_data' table, each row contains:
        - frame: The simulation frame.
        - agent_id: The identifier of the agent.
        - area: The area where the agent is located.
        - risk: The risk value (between 0 and 1) for that area/frame.

    The combined risk for an agent is computed as:
        combined_risk = 1 - ∏ (1 - risk)
    across all rows (frames/areas) associated with that agent.

    The function then returns the average combined risk across all agents, rounded up to one decimal place.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        float: The average combined risk across all agents, rounded up to one decimal place.

    Raises:
        RuntimeError: If there is an error retrieving the data.
        ValueError: If any risk value is not between 0 and 1.
    """
    try:
        query = "SELECT agent_id, risk FROM agent_area_data;"
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        # Dictionary to accumulate the product of complements for each agent
        agent_product = defaultdict(lambda: 1.0)

        for agent_id, risk in rows:
            if risk is None or not (0 <= risk <= 1):
                raise ValueError(f"Invalid risk value: {risk}")
            agent_product[agent_id] *= (1 - risk)

        total_combined_risk = 0.0
        count = 0

        # Calculate combined risk per agent and accumulate the sum
        for agent_id, product in agent_product.items():
            combined_risk = 1 - product
            total_combined_risk += combined_risk
            count += 1

        if count == 0:
            return 0.0

        average_risk = total_combined_risk / count
        return math.ceil(average_risk * 10) / 10

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving agent risk data: {e}")

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
