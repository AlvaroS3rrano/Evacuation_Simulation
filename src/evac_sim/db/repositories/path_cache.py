import json
import sqlite3


def upsert_path(
    connection: sqlite3.Connection,
    source: str,
    target: str,
    cost: float,
    path: list[str],
    betweenness: float | None = None,
):
    path_json = json.dumps(path)

    with connection:
        connection.execute(
            """
            INSERT INTO paths (source, target, cost, path, betweenness)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source, target, path)
            DO UPDATE SET
                cost = excluded.cost,
                betweenness = excluded.betweenness
            """,
            (source, target, cost, path_json, betweenness),
        )


def get_path(
    connection: sqlite3.Connection,
    source: str,
    target: str,
):
    cursor = connection.cursor()

    row = cursor.execute(
        """
        SELECT cost, path, betweenness
        FROM paths
        WHERE source = ? AND target = ?
        """,
        (source, target),
    ).fetchone()

    if row is None:
        return None

    cost, path_json, betweenness = row

    return {
        "cost": cost,
        "path": json.loads(path_json),
        "betweenness": betweenness,
    }

def get_paths(
    connection: sqlite3.Connection,
    source: str,
    target: str,
):
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT cost, path, betweenness
        FROM paths
        WHERE source = ? AND target = ?
        ORDER BY cost ASC, betweenness DESC, path ASC
        """,
        (source, target),
    ).fetchall()

    return [
        {
            "cost": cost,
            "path": json.loads(path_json),
            "betweenness": betweenness,
        }
        for cost, path_json, betweenness in rows
    ]


def find_paths_containing_node(
    connection: sqlite3.Connection,
    node: str,
):
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT source, target, path
        FROM paths
        """
    ).fetchall()

    results = []

    for source, target, path_json in rows:
        path = json.loads(path_json)
        if node in path:
            results.append((source, target, path))

    return results