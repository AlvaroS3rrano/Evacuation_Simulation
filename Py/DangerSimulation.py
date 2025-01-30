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
def update_risk(G, propagation_chance=0.3, decrease_chance=0.2):
    """
    Actualiza los niveles de riesgo de los nodos en el grafo, reduciendo el riesgo hacia 0 (más peligroso).

    Parámetros:
        G (nx.DiGraph): Grafo con nodos y conexiones.
        propagation_chance (float): Probabilidad de propagar riesgo a vecinos.
        decrease_chance (float): Probabilidad de disminuir el nivel de seguridad del nodo.
    """
    new_risks = {}

    for node in G.nodes:
        current_risk = G.nodes[node]["risk"]

        # Reducir el nivel de seguridad del nodo
        if random.random() < decrease_chance:
            current_risk = max(0.0, current_risk - random.uniform(0.05, 0.2))  # Reducir el riesgo propio

        # Redondear a un decimal el riesgo propio
        new_risks[node] = round(current_risk, 1)

        # Propagación del riesgo a los vecinos
        for neighbor in G.neighbors(node):
            if random.random() < propagation_chance:
                # propagated_risk = G.nodes[node]["risk"] * random.uniform(0.1, 0.5)
                propagated_risk = (1 - G.nodes[node]["risk"]) * random.uniform(0.1, 0.5)
                neighbor_risk = G.nodes[neighbor]["risk"]
                new_risk = max(0.0, neighbor_risk - propagated_risk)  # Reducir el riesgo del vecino

                # Redondear a un decimal el riesgo propagado
                new_risks[neighbor] = round(new_risk, 1)

    # Aplicar los nuevos riesgos
    for node, risk in new_risks.items():
        G.nodes[node]["risk"] = risk

# Crear el grafo
G = nx.DiGraph()

# Nodos y sus niveles iniciales de riesgo (0 a 1)
nodes = {
    "A": 0.2, "B": 0.1, "C": 0.0,
    "D": 0.0, "E": 0.3, "F": 0.0,
    "G": 0.5, "H": 0.0, "I": 0.0,
}

# Agregar nodos al grafo
for node, risk in nodes.items():
    G.add_node(node, risk=risk)

# Definir las conexiones entre nodos
edges = [
    ("A", "B"), ("A", "F"), ("B", "A"), ("B", "E"), ("B", "C"),
    ("C", "B"), ("C", "D"), ("D", "I"), ("D", "E"), ("D", "C"),
    ("E", "D"), ("E", "F"), ("E", "B"), ("E", "H"), ("F", "A"),
    ("F", "E"), ("F", "G"), ("G", "F"), ("G", "H"), ("H", "E"),
    ("H", "G"), ("H", "I"),
]

# Agregar las aristas con un costo fijo (se puede ajustar)
G.add_edges_from([(u, v, {"cost": 3}) for u, v in edges])