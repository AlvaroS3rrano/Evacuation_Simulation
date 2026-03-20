import sqlite3

from evac_sim.db.repositories.group_decisions import (
    get_group_decision,
    get_group_decisions_by_frame,
    get_group_decisions_dataframe,
    insert_group_decision,
)
from evac_sim.db.schema import create_group_decisions_table


def test_insert_and_get_group_decision():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection=connection,
        frame=1,
        group_id=10,
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

    result = get_group_decision(connection, 1, 10, "shortest", "high")

    assert result is not None
    assert result["current_area"] == "A"
    assert result["next_path"] == ["A", "B", "C"]
    assert result["risk_now"] == 0.3


def test_get_group_decisions_by_frame_filters_optionally():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection, 1, 1, "shortest", "high", "A", ["A", "B"], 0.2, 0.3, 0.1, 0.01, 0.2
    )
    insert_group_decision(
        connection, 1, 2, "centrality", "low", "C", ["C", "D"], 0.4, 0.5, 0.2, 0.02, 0.4
    )

    df = get_group_decisions_by_frame(connection, frame=1, algorithm="shortest")

    assert len(df) == 1
    assert df.iloc[0]["group_id"] == 1
    assert df.iloc[0]["next_path"] == ["A", "B"]


def test_get_group_decisions_dataframe_parses_next_path():
    connection = sqlite3.connect(":memory:")
    create_group_decisions_table(connection)

    insert_group_decision(
        connection, 2, 7, "shortest", "low", "X", ["X", "Y"], 0.1, 0.2, 0.0, 0.01, 0.1
    )

    df = get_group_decisions_dataframe(connection)

    assert len(df) == 1
    assert df.iloc[0]["next_path"] == ["X", "Y"]