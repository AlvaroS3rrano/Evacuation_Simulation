import sqlite3

from evac_sim.db.repositories.risk import (
    get_risk_dataframe,
    get_risk_levels_by_frame,
    insert_risk_levels,
)
from evac_sim.db.schema import create_risk_table


def test_insert_and_get_risk_levels_by_frame():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, "case_1", 1, {"A": 0.2, "B": 0.7})

    result = get_risk_levels_by_frame(connection, "case_1", 1)

    assert result == {"A": 0.2, "B": 0.7}


def test_get_risk_levels_by_frame_returns_empty_for_missing_case():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, "case_1", 1, {"A": 0.2})

    result = get_risk_levels_by_frame(connection, "case_2", 1)

    assert result == {}


def test_get_risk_dataframe_returns_expected_columns():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, "case_1", 1, {"A": 0.2})

    df = get_risk_dataframe(connection, "case_1")

    assert list(df.columns) == ["frame", "area", "risk_level"]
    assert len(df) == 1
    assert df.iloc[0]["frame"] == 1
    assert df.iloc[0]["area"] == "A"
    assert df.iloc[0]["risk_level"] == 0.2


def test_get_risk_dataframe_filters_by_case_name():
    connection = sqlite3.connect(":memory:")
    create_risk_table(connection)

    insert_risk_levels(connection, "case_1", 1, {"A": 0.2})
    insert_risk_levels(connection, "case_2", 1, {"B": 0.8})

    df = get_risk_dataframe(connection, "case_1")

    assert len(df) == 1
    assert df.iloc[0]["area"] == "A"