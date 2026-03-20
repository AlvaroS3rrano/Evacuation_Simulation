import numpy as np
import pandas as pd
import sqlite3
from typing import Any
import networkx as nx

from evac_sim.db.repositories.agent_area import get_average_normalized_risk_exposure_by_group


def p90(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.array(values, dtype=float), 90))

def path_cost(graph: nx.Graph, path: list[Any]) -> float:
    if not path or len(path) < 2:
        return 0.0

    total_cost = 0.0
    for u, v in zip(path, path[1:]):
        if not graph.has_edge(u, v):
            raise RuntimeError(
                f"Edge ({u}, {v}) not found while computing cost for path {path}"
            )

        edge_data = graph[u][v]
        cost = edge_data.get("cost")
        if cost is None:
            raise RuntimeError(
                f"Edge ({u}, {v}) is missing the 'cost' attribute for path {path}"
            )

        total_cost += float(cost)

    return total_cost

def compute_group_metrics(
    *,
    graph: nx.Graph,
    group_path_df: pd.DataFrame,
    agent_area_conn: sqlite3.Connection,
    group_id: Any,
    agent_ids: list[int],
    per_agent_times: list[float],
) -> dict[str, Any]:
    gdf = group_path_df[group_path_df["group_id"].astype(str) == str(group_id)].copy()
    n_records = int(len(gdf))

    mean_remaining_path_risk = float(gdf["est_risk_mean"].mean()) if n_records else 0.0
    remaining_path_risk_var = float(gdf["est_risk_var"].mean()) if n_records else 0.0

    if n_records and "next_path" in gdf.columns:
        avg_path_cost = float(
            gdf["next_path"].apply(
                lambda p: path_cost(graph, p) if isinstance(p, list) else 0.0
            ).mean()
        )
    else:
        avg_path_cost = 0.0

    cumulative_risk_exposure = float(
        get_average_normalized_risk_exposure_by_group(agent_area_conn, agent_ids)
    )

    if per_agent_times:
        min_time = float(min(per_agent_times))
        avg_time = float(sum(per_agent_times) / len(per_agent_times))
        median_time = float(np.median(np.array(per_agent_times, dtype=float)))
        p90_time = p90(per_agent_times)
        max_time = float(max(per_agent_times))
    else:
        min_time = avg_time = median_time = p90_time = max_time = 0.0

    return {
        "n_records": n_records,
        "mean_remaining_path_risk": mean_remaining_path_risk,
        "remaining_path_risk_var": remaining_path_risk_var,
        "cumulative_risk_exposure": cumulative_risk_exposure,
        "avg_path_cost": avg_path_cost,
        "min_time": min_time,
        "avg_time": avg_time,
        "median_time": median_time,
        "p90_time": p90_time,
        "max_time": max_time,
    }