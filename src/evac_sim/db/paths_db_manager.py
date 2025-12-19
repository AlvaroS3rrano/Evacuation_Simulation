import json
import sqlite3
from typing import List

import pandas as pd


def create_paths_table(connection: sqlite3.Connection, force_reset: bool = False) -> None:
    """
    Creates the 'paths' table if it doesn't exist.
    If force_reset=True, drops and recreates the table.
    """
    try:
        with connection:
            if force_reset:
                connection.execute("DROP TABLE IF EXISTS paths")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source INTEGER NOT NULL,
                    target INTEGER NOT NULL,
                    cost INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    betweenness REAL NOT NULL
                )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating paths table: {e}")

def insert_path(connection: sqlite3.Connection, source: int, target: int, cost: int, path: List[int], betweenness: float):
    """
    Insert or update a path between two nodes in the database, along with its betweenness centrality.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        source (int): The source node.
        target (int): The target node.
        cost (int): The cost of the path.
        path (List[int]): A list of nodes representing the path between source and target.
        betweenness (float): The betweenness centrality score for the path.
    """
    try:
        with connection:
            # Convert the path list to a JSON string
            path_str = json.dumps(path)
            connection.execute(
                "INSERT OR REPLACE INTO paths (source, target, cost, path, betweenness) VALUES (?, ?, ?, ?, ?)",
                (source, target, cost, path_str, betweenness)
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error inserting the path between {source} and {target}: {e}")

def find_paths_containing_node(connection: sqlite3.Connection, node: int):
    """
    Query paths that contain a specific node, excluding it from being source or target.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        node (int): The node that must be part of the path, but not the source or target.

    Returns:
        pd.DataFrame: DataFrame containing paths that include the node.
    """
    try:
        query = """
        SELECT * 
        FROM paths
        WHERE path LIKE ? 
        AND source != ? 
        AND target != ?
        """
        # Use the node's representation in the path as a string
        path_pattern = f'%"{node}"%'  # Look for the node as part of the path
        return pd.read_sql_query(query, connection, params=(path_pattern, node, node))
    except Exception as e:
        raise RuntimeError(f"Error finding paths that contain node {node}: {e}")

def read_all_paths(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Reads all paths stored in the paths table.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.

    Returns:
        pd.DataFrame: A DataFrame containing all the paths data.
    """
    try:
        query = "SELECT * FROM paths"
        return pd.read_sql_query(query, connection)
    except Exception as e:
        raise RuntimeError(f"Error reading all paths: {e}")

def read_paths_by_source_target(connection: sqlite3.Connection, source: int, target: int) -> pd.DataFrame:
    """
    Reads the paths stored in the paths table for a specific source and target.

    Args:
        connection (sqlite3.Connection): An open SQLite database connection.
        source (int): The source node.
        target (int): The target node.

    Returns:
        pd.DataFrame: A DataFrame containing the paths between the source and target.
    """
    try:
        query = "SELECT * FROM paths WHERE source = ? AND target = ?"
        return pd.read_sql_query(query, connection, params=(source, target))
    except Exception as e:
        raise RuntimeError(f"Error reading paths for source {source} and target {target}: {e}")
