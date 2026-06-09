from __future__ import annotations

import math
from typing import Any

from evac_sim.orchestration.congestion_config import CongestionConfig
from evac_sim.simulation.temporal_capacity import reset_temporal_capacity_state


def apply_edge_flow_capacity_multiplier(
    graph: Any,
    multiplier: float,
) -> None:
    """
    Apply a multiplier to edge flow_capacity values.

    The original value is preserved in base_flow_capacity.
    """
    if multiplier <= 0:
        raise ValueError("Edge flow capacity multiplier must be > 0")

    for _, _, edge_data in graph.edges(data=True):
        base_flow_capacity = int(
            edge_data.get(
                "base_flow_capacity",
                edge_data.get("flow_capacity", 1),
            )
        )

        edge_data["base_flow_capacity"] = max(1, base_flow_capacity)
        edge_data["flow_capacity"] = max(
            1,
            int(math.ceil(edge_data["base_flow_capacity"] * multiplier)),
        )
        edge_data["flow_capacity_multiplier"] = multiplier
        edge_data.setdefault("flow_occupancy", 0)


def apply_node_capacity_multiplier(
    graph: Any,
    congestion_config: CongestionConfig,
) -> None:
    """
    Apply a multiplier to node_capacity values.

    The original value is preserved in base_node_capacity.
    """
    multiplier = congestion_config.node_capacity_multiplier

    if multiplier <= 0:
        raise ValueError("Node capacity multiplier must be > 0")

    temporal_cfg = congestion_config.temporal_capacity

    for _, node_data in graph.nodes(data=True):
        base_node_capacity = int(
            node_data.get(
                "base_node_capacity",
                node_data.get(
                    "node_capacity",
                    temporal_cfg.node_capacity_default,
                ),
            )
        )

        node_data["base_node_capacity"] = max(1, base_node_capacity)
        node_data["node_capacity"] = max(
            1,
            int(math.ceil(node_data["base_node_capacity"] * multiplier)),
        )
        node_data["node_capacity_multiplier"] = multiplier
        node_data.setdefault("node_occupancy", 0)


def apply_temporal_capacity_settings_to_graph(
    graph: Any,
    congestion_config: CongestionConfig,
) -> None:
    """
    Attach temporal h3 capacity configuration and reset temporal reservations.
    """
    graph.graph["temporal_capacity_config"] = congestion_config.temporal_capacity
    reset_temporal_capacity_state(graph)


def apply_congestion_settings_to_graph(
    graph: Any,
    congestion_config: CongestionConfig,
) -> None:
    """
    Apply congestion settings to the copied graph used by one simulation run.
    """
    apply_node_capacity_multiplier(
        graph,
        congestion_config,
    )

    apply_edge_flow_capacity_multiplier(
        graph,
        congestion_config.edge_flow_capacity_multiplier,
    )

    for _, _, edge_data in graph.edges(data=True):
        edge_data["use_linear_congestion_cost"] = (
            congestion_config.use_linear_congestion_cost
        )
        edge_data["block_edges_at_capacity"] = (
            congestion_config.block_edges_at_capacity
        )

    apply_temporal_capacity_settings_to_graph(
        graph,
        congestion_config,
    )