import sqlite3

from evac_sim.db.schema import create_agent_area_table
from evac_sim.db.repositories.agent_area import insert_agent_areas, get_agent_areas_by_frame, get_average_normalized_risk_exposure_by_group


def test_create_agent_area_table():
    conn = sqlite3.connect(":memory:")

    create_agent_area_table(conn)

    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_area_data'"
    )

    result = cursor.fetchone()

    assert result is not None

def test_insert_agent_areas():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    insert_agent_areas(
        conn,
        frame=1,
        agent_areas={
            1: ("A", 0.2),
            2: ("B", 0.5),
        },
    )

    rows = conn.execute(
        "SELECT frame, agent_id, area, risk_level FROM agent_area_data"
    ).fetchall()

    assert len(rows) == 2

    assert (1, 1, "A", 0.2) in rows
    assert (1, 2, "B", 0.5) in rows

def test_get_agent_areas_by_frame():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    insert_agent_areas(
        conn,
        frame=3,
        agent_areas={
            10: ("X", 0.3),
            11: ("Y", 0.7),
        },
    )

    rows = get_agent_areas_by_frame(conn, 3)

    assert len(rows) == 2
    assert (10, "X", 0.3) in rows
    assert (11, "Y", 0.7) in rows

def test_average_risk_exposure():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    insert_agent_areas(
        conn,
        frame=1,
        agent_areas={
            1: ("A", 0.2),
            2: ("B", 0.6),
        },
    )

    avg = get_average_normalized_risk_exposure_by_group(conn, [1, 2])

    assert abs(avg - 0.4) < 1e-6

def test_average_risk_exposure_empty():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    avg = get_average_normalized_risk_exposure_by_group(conn, [])

    assert avg == 0.0