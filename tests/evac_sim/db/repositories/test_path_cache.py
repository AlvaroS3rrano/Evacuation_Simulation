import sqlite3

from evac_sim.db.schema import create_paths_table
from evac_sim.db.repositories.path_cache import upsert_path, get_path

def test_insert_and_get_path():
    conn = sqlite3.connect(":memory:")
    create_paths_table(conn)

    upsert_path(conn, "A", "B", 5.0, ["A","C","B"])

    path = get_path(conn, "A", "B")

    assert path["cost"] == 5.0
    assert path["path"] == ["A","C","B"]