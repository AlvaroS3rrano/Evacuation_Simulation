from __future__ import annotations

import math
from typing import Any

from evac_sim.orchestration.congestion_config import CongestionConfig
from evac_sim.simulation.temporal_capacity import reset_temporal_capacity_state


def apply_edge_capacity_multiplier(
    graph: Any,
    multiplier: float,
) -> None:
    """
    Apply a capacity multiplier to all graph edges.

    The original edge capacity is preserved in `base_capacity`.
    If multiplier is 1.0, capacities are left unchanged.
    """

    if multiplier <= 0:
        raise ValueError("Edge capacity multiplier must be > 0")

    if multiplier == 1.0:
        return

    for _, _, edge_data in graph.edges(data=True):
        base_capacity = int(
            edge_data.get(
                "base_capacity",
                edge_data.get("capacity", 1),
            )
        )

        edge_data["base_capacity"] = base_capacity
        edge_data["capacity"] = max(
            1,
            int(math.ceil(base_capacity * multiplier)),
        )
        edge_data["capacity_multiplier"] = multiplier


def apply_temporal_capacity_settings_to_graph(
    graph: Any,
    congestion_config: CongestionConfig,
) -> None:
    """
    Attach temporal node/edge capacity settings to the graph used by a run.

    This keeps h3 separate from the old h1/h2 edge occupancy model.
    """

    temporal_cfg = congestion_config.temporal_capacity

    graph.graph["temporal_capacity_config"] = temporal_cfg
    reset_temporal_capacity_state(graph)

    for _, _, edge_data in graph.edges(data=True):
        base_flow_capacity = int(
            edge_data.get(
                "base_flow_capacity",
                edge_data.get(
                    "flow_capacity",
                    edge_data.get(
                        "capacity",
                        temporal_cfg.edge_flow_capacity_default,
                    ),
                ),
            )
        )

        edge_data["base_flow_capacity"] = max(1, base_flow_capacity)
        edge_data["flow_capacity"] = max(
            1,
            int(math.ceil(edge_data["base_flow_capacity"])),
        )

    for _, node_data in graph.nodes(data=True):
        base_node_capacity = int(
            node_data.get(
                "base_node_capacity",
                node_data.get(
                    "node_capacity",
                    node_data.get(
                        "capacity",
                        temporal_cfg.node_capacity_default,
                    ),
                ),
            )
        )

        node_data["base_node_capacity"] = max(1, base_node_capacity)
        node_data["node_capacity"] = max(
            1,
            int(math.ceil(node_data["base_node_capacity"])),
        )


def apply_congestion_settings_to_graph(
    graph: Any,
    congestion_config: CongestionConfig,
) -> None:
    """
    Apply congestion-related simulation settings to graph edges.

    This does not modify the environment definition itself, only the copied graph
    used by the current simulation.
    """

    apply_edge_capacity_multiplier(
        graph,
        congestion_config.edge_capacity_multiplier,
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