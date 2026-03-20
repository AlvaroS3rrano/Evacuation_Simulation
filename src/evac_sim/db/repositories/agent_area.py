def insert_agent_areas(
    connection,
    case_name: str,
    mode: int,
    frame: int,
    agent_areas: dict[int, tuple[str, float]],
):
    rows = [
        (case_name, mode, frame, agent_id, area, risk)
        for agent_id, (area, risk) in agent_areas.items()
    ]

    connection.executemany(
        """
        INSERT OR REPLACE INTO agent_area_data
        (case_name, mode, frame, agent_id, area, risk_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def get_average_normalized_risk_exposure_by_group(
    connection,
    case_name: str,
    mode: int,
    agent_ids,
):
    if not agent_ids:
        return 0.0

    placeholders = ",".join("?" for _ in agent_ids)

    rows = connection.execute(
        f"""
        SELECT risk_level
        FROM agent_area_data
        WHERE case_name = ? AND mode = ? AND agent_id IN ({placeholders})
        """,
        (case_name, mode, *agent_ids),
    ).fetchall()

    if not rows:
        return 0.0

    risks = [r[0] for r in rows]
    return sum(risks) / len(risks)