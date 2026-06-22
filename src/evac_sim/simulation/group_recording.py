from __future__ import annotations

from statistics import mean, pvariance

from evac_sim.core.agent_group import AgentGroup
from evac_sim.db.repositories.group_decisions import insert_group_decision


def record_group_path_data(
    connection,
    *,
    case_name: str,
    mode: int,
    frame: int,
    group_id: str,
    group: AgentGroup,
    risks: dict,
) -> None:
    algorithm = "Centrality" if group.algorithm == 1 else "Efficient"
    awareness = "High" if group.awareness_level == 1 else "Low"

    path = group.path or []

    max_idx = -1
    current_area = None

    for aid in group.agents:
        area = group.current_nodes.get(aid)

        if area is None:
            continue

        try:
            idx = path.index(area)
        except ValueError:
            idx = -1

        if idx > max_idx:
            max_idx = idx
            current_area = area

    if current_area is None and group.agents:
        current_area = group.current_nodes.get(group.agents[0])

    next_path = path[max_idx:] if max_idx >= 0 else path
    risk_values = [risks.get(area, 0.0) for area in next_path]

    insert_group_decision(
        connection,
        case_name=case_name,
        mode=mode,
        frame=frame,
        group_id=str(group_id),
        algorithm=algorithm,
        awareness=awareness,
        current_area=current_area,
        next_path=next_path,
        est_risk_mean=mean(risk_values) if risk_values else 0.0,
        est_risk_max=max(risk_values) if risk_values else 0.0,
        est_risk_min=min(risk_values) if risk_values else 0.0,
        est_risk_var=pvariance(risk_values) if len(risk_values) > 1 else 0.0,
        risk_now=risks.get(current_area, 0.0) if current_area is not None else 0.0,
    )