import sqlite3

from evac_sim.db.schema import create_agent_area_table
from evac_sim.db.repositories.agent_area import (
    insert_agent_areas,
    get_average_normalized_risk_exposure_by_group,
)


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
        case_name="case_1",
        mode=0,
        frame=1,
        agent_areas={
            1: ("A", 0.2),
            2: ("B", 0.5),
        },
    )

    rows = conn.execute(
        """
        SELECT case_name, mode, frame, agent_id, area, risk_level
        FROM agent_area_data
        ORDER BY agent_id
        """
    ).fetchall()

    assert len(rows) == 2
    assert ("case_1", 0, 1, 1, "A", 0.2) in rows
    assert ("case_1", 0, 1, 2, "B", 0.5) in rows


def test_average_risk_exposure():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    insert_agent_areas(
        conn,
        case_name="case_1",
        mode=1,
        frame=1,
        agent_areas={
            1: ("A", 0.2),
            2: ("B", 0.6),
            3: ("C", 0.9),
        },
    )

    avg = get_average_normalized_risk_exposure_by_group(
        conn,
        case_name="case_1",
        mode=1,
        agent_ids=[1, 2],
    )

    assert abs(avg - 0.4) < 1e-6


def test_average_risk_exposure_empty():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    avg = get_average_normalized_risk_exposure_by_group(
        conn,
        case_name="case_1",
        mode=0,
        agent_ids=[],
    )

    assert avg == 0.0


def test_average_risk_exposure_returns_zero_when_group_not_found():
    conn = sqlite3.connect(":memory:")
    create_agent_area_table(conn)

    insert_agent_areas(
        conn,
        case_name="case_1",
        mode=0,
        frame=1,
        agent_areas={
            1: ("A", 0.2),
        },
    )

    avg = get_average_normalized_risk_exposure_by_group(
        conn,
        case_name="case_2",
        mode=0,
        agent_ids=[1],
    )

    assert avg == 0.0