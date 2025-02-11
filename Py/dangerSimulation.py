import sqlite3
import networkx as nx
import random
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
            risk_data = [(frame, area, risk) for area, risk in risks.items()]
            connection.executemany(
                "INSERT OR REPLACE INTO risk_data (frame, area, risk_level) VALUES (?, ?, ?)",
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


def get_risks_grouped_by_frame(connection: sqlite3.Connection) -> dict:
    """
    Retrieves a nested dictionary where each frame maps to a dictionary of areas and risk levels.

    Args:
        connection (sqlite3.Connection): Open SQLite database connection.

    Returns:
        dict: {frame: {area: risk_level, ...}, ...}

    Raises:
        RuntimeError: If there is an error fetching data.
    """
    try:
        query = "SELECT frame, area, risk_level FROM risk_data ORDER BY frame, area"
        cursor = connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()

        # Grouping results into a nested dictionary
        risks_per_frame = defaultdict(dict)
        for frame, area, risk_level in results:
            risks_per_frame[frame][area] = risk_level  # Nesting areas inside each frame

        return dict(risks_per_frame)  # Convert defaultdict to a normal dict
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
def update_risk(G: nx.DiGraph, propagation_chance=0.3, increase_chance=0.2):
    """
    Updates the risk levels of nodes in the graph, increasing the risk towards 1 (more dangerous).

    Args:
        G (nx.DiGraph): Graph with nodes and edges.
        propagation_chance (float): Probability of risk spreading to neighbors.
        increase_chance (float): Probability of increasing the node's risk level.
    """
    new_risks = {}

    for node in G.nodes:
        current_risk = G.nodes[node]["risk"]

        # Increase the risk of the node (making it more dangerous)
        if random.random() < increase_chance:
            current_risk = min(1.0, current_risk + random.uniform(0.05, 0.2))  # Increase risk

        # Round risk to 1 decimal place
        new_risks[node] = round(current_risk, 1)

        # Risk propagation to neighbors
        for neighbor in G.neighbors(node):
            if random.random() < propagation_chance:
                # Compute risk increase based on the current node's risk
                propagated_risk = G.nodes[node]["risk"] * random.uniform(0.1, 0.5)
                neighbor_risk = G.nodes[neighbor]["risk"]
                new_risk = min(1.0, neighbor_risk + propagated_risk)  # Increase neighbor's risk

                # Round propagated risk to 1 decimal place
                new_risks[neighbor] = round(new_risk, 1)

    # Apply the new risk values to the graph
    for node, risk in new_risks.items():
        G.nodes[node]["risk"] = risk