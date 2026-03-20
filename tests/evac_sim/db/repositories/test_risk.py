import sqlite3

from evac_sim.db.repositories.risk import (
    get_all_risks,
    get_risk_dataframe,
    get_risk_levels_by_frame,
    get_risks_grouped_by_frame,
    insert_risk_levels,
)
from evac_sim.db.schema import create_risk_table


def test_insert_and_get_risk_levels_by_frame():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, 1, {"A": 0.2, "B": 0.7})

    result = get_risk_levels_by_frame(connection, 1)

    assert result == {"A": 0.2, "B": 0.7}


def test_get_all_risks_returns_sorted_rows():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, 2, {"B": 0.8})
    insert_risk_levels(connection, 1, {"A": 0.2})

    result = get_all_risks(connection)

    assert result == [
        (1, "A", 0.2),
        (2, "B", 0.8),
    ]


def test_get_risks_grouped_by_frame():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, 1, {"A": 0.2, "B": 0.7})
    insert_risk_levels(connection, 2, {"A": 0.5})

    result = get_risks_grouped_by_frame(connection)

    assert result == {
        1: {"A": 0.2, "B": 0.7},
        2: {"A": 0.5},
    }


def test_get_risk_dataframe_returns_expected_columns():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, 1, {"A": 0.2})

    df = get_risk_dataframe(connection)

    assert list(df.columns) == ["frame", "area", "risk_level"]
    assert len(df) == 1