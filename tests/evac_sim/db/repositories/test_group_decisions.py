import sqlite3

from evac_sim.db.repositories.group_decisions import (
    get_group_decisions_dataframe,
    insert_group_decision,
)
from evac_sim.db.schema import create_group_decisions_table


def test_insert_group_decision():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection=connection,
        case_name="case_1",
        mode=0,
        frame=1,
        group_id="10",
        algorithm="shortest",
        awareness="high",
        current_area="A",
        next_path=["A", "B", "C"],
        est_risk_mean=0.2,
        est_risk_max=0.4,
        est_risk_min=0.1,
        est_risk_var=0.01,
        risk_now=0.3,
    )

    rows = connection.execute(
        """
        SELECT case_name, mode, frame, group_id, algorithm, awareness, current_area,
               next_path, est_risk_mean, est_risk_max, est_risk_min, est_risk_var, risk_now
        FROM group_path_data
        """
    ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "case_1"
    assert row[1] == 0
    assert row[2] == 1
    assert row[3] == "10"
    assert row[4] == "shortest"
    assert row[5] == "high"
    assert row[6] == "A"
    assert row[8] == 0.2
    assert row[12] == 0.3


def test_get_group_decisions_dataframe_parses_next_path():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection=connection,
        case_name="case_1",
        mode=0,
        frame=2,
        group_id="7",
        algorithm="shortest",
        awareness="low",
        current_area="X",
        next_path=["X", "Y"],
        est_risk_mean=0.1,
        est_risk_max=0.2,
        est_risk_min=0.0,
        est_risk_var=0.01,
        risk_now=0.1,
    )

    df = get_group_decisions_dataframe(connection, case_name="case_1", mode=0)

    assert len(df) == 1
    assert df.iloc[0]["frame"] == 2
    assert df.iloc[0]["group_id"] == "7"
    assert df.iloc[0]["next_path"] == ["X", "Y"]


def test_get_group_decisions_dataframe_filters_by_case_and_mode():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection,
        "case_1",
        0,
        1,
        "1",
        "shortest",
        "high",
        "A",
        ["A", "B"],
        0.2,
        0.3,
        0.1,
        0.01,
        0.2,
    )
    insert_group_decision(
        connection,
        "case_1",
        1,
        1,
        "2",
        "centrality",
        "low",
        "C",
        ["C", "D"],
        0.4,
        0.5,
        0.2,
        0.02,
        0.4,
    )
    insert_group_decision(
        connection,
        "case_2",
        0,
        1,
        "3",
        "shortest",
        "low",
        "E",
        ["E", "F"],
        0.3,
        0.4,
        0.2,
        0.01,
        0.3,
    )

    df = get_group_decisions_dataframe(connection, case_name="case_1", mode=0)

    assert len(df) == 1
    assert df.iloc[0]["group_id"] == "1"
    assert df.iloc[0]["next_path"] == ["A", "B"]