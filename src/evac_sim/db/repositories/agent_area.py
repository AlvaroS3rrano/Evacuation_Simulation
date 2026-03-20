def insert_agent_areas(connection, frame: int, agent_areas: dict[int, tuple[str, float]]):
    with connection:
        rows = [
            (frame, agent_id, area, risk)
            for agent_id, (area, risk) in agent_areas.items()
        ]

        connection.executemany(
            """
            INSERT OR REPLACE INTO agent_area_data
            (frame, agent_id, area, risk_level)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )

def get_agent_areas_by_frame(connection, frame: int):
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT agent_id, area, risk_level
        FROM agent_area_data
        WHERE frame = ?
        """,
        (frame,),
    ).fetchall()

    return rows

def get_average_normalized_risk_exposure_by_group(connection, agent_ids):
    cursor = connection.cursor()

    placeholders = ",".join("?" for _ in agent_ids)

    rows = cursor.execute(
        f"""
        SELECT risk_level
        FROM agent_area_data
        WHERE agent_id IN ({placeholders})
        """,
        tuple(agent_ids),
    ).fetchall()

    if not rows:
        return 0.0

    risks = [r[0] for r in rows]

    return sum(risks) / len(risks)