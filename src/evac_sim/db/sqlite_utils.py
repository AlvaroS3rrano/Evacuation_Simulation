from pathlib import Path
from typing import Optional, Callable
import pandas as pd
import sqlite3


def init_db_connection(
    db_file: Path,
    create_fn: Optional[Callable[[sqlite3.Connection], None]] = None,
) -> sqlite3.Connection:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file))
    if create_fn is not None:
        create_fn(conn)
    return conn

def read_sqlite_fps(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT value FROM metadata WHERE key = ?", ("fps",)).fetchone()
    if row is None:
        raise RuntimeError("Trajectory DB missing metadata.fps")
    return float(row[0])


def read_trajectory_dataframe(trajectory_db_file: Path) -> tuple[pd.DataFrame, float]:
    conn = sqlite3.connect(str(trajectory_db_file))
    try:
        tables_df = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            conn,
        )
        table_names = set(tables_df["name"].tolist())

        trajectory_table = next(
            (name for name in ["trajectory_data", "trajectory", "trajectories"] if name in table_names),
            None,
        )
        if trajectory_table is None:
            raise RuntimeError(
                f"No trajectory table found in {trajectory_db_file}. Available tables: {sorted(table_names)}"
            )

        fps = read_sqlite_fps(conn)
        df = pd.read_sql_query(
            f"SELECT frame, id, pos_x, pos_y FROM {trajectory_table}",
            conn,
        )
    finally:
        conn.close()

    if not df.empty:
        df["frame"] = df["frame"].astype(float)
        df["id"] = df["id"].astype(int)
        df["pos_x"] = df["pos_x"].astype(float)
        df["pos_y"] = df["pos_y"].astype(float)

    return df, fps

def compute_times_from_trajectory_sqlite(
    trajectory_db_file: Path,
    agent_ids: list[int],
) -> list[float]:
    """
    Compute per-agent evacuation times from the JuPedSim trajectory SQLite output,
    using the FPS written by JuPedSim into the trajectory database metadata.
    """
    if not agent_ids:
        return []

    conn = sqlite3.connect(str(trajectory_db_file))
    try:
        tables_df = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            conn,
        )
        table_names = set(tables_df["name"].tolist())

        trajectory_table = next(
            (name for name in ["trajectory_data", "trajectory", "trajectories"] if name in table_names),
            None,
        )

        if trajectory_table is None:
            raise RuntimeError(
                f"No trajectory table found in {trajectory_db_file}. "
                f"Available tables: {sorted(table_names)}"
            )

        fps = read_sqlite_fps(conn)
        ids_str = ",".join(str(int(a)) for a in agent_ids)

        query = f"""
            SELECT id, MAX(frame) AS max_frame
            FROM {trajectory_table}
            WHERE id IN ({ids_str})
            GROUP BY id
        """

        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        return []

    return (df["max_frame"].astype(float) / fps).tolist()