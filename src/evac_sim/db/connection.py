import sqlite3
from pathlib import Path

def get_connection(db_path: str | Path ):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn