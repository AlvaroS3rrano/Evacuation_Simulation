import itertools
import logging
import math
from typing import Any

import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths

from evac_sim.simulation.capacity_reservations import get_capacity_reservation_manager

logger = logging.getLogger(__name__)


def compute_path_base_cost(G, path) -> float:
    """
    Compute the static base cost of a path.

    This is used for candidate generation and cache storage. Dynamic heuristics
    rescore the same candidate paths later using the current congestion state.
    """
    if not path or len(path) < 2:
        return float("inf")

    return sum(float(G[u][v]["cost"]) for u, v in zip(path, path[1:]))


def compute_path_effective_cost(
    G,
    path,
    *,
    heuristic: str = "none",
    group_size: int = 0,
    horizon_k: int | None = None,
    group_id: Any | None = None,
) -> float:
    """
    Compute the effective cost of a complete path.

    For none:
        The base edge cost is used.

    For h1:
        The path is evaluated using full-path temporal capacity reservations.

    For h2:
        The path is evaluated using temporal capacity reservations only over the
        next horizon_k edges.

    For h3:
        The path is evaluated as an earliest-feasible-arrival schedule using
        temporal reservations.

    Important:
        This function only scores the path. It does not reserve it. The actual
        reservation must be done by CapacityReservationManager before the group
        is allowed to move.
    """
    if not path or len(path) < 2:
        return float("inf")

    if heuristic == "none":
        return compute_path_base_cost(G, path)

    if heuristic in {"h1", "h2", "h3"}:
        current_frame = int(G.graph.get("current_frame", 0))
        manager = get_capacity_reservation_manager(G)

        horizon_edges = None

        if heuristic == "h2":
            if horizon_k is None:
                raise ValueError("horizon_k must be provided when heuristic='h2'")
            horizon_edges = horizon_k

        return manager.earliest_arrival_cost(
            list(path),
            group_size=group_size,
            start_frame=current_frame,
            horizon_edges=horizon_edges,
            ignore_group_id=group_id,
        )

    raise ValueError(f"Unknown heuristic: {heuristic}")


def centrality_measures(G, all_paths):
    """
    Compute node centrality over a candidate path set and assign each path a
    geometric-mean score based on its interior nodes.
    """
    node_centrality = {node: 0.0 for node in G.nodes()}
    total_paths = len(all_paths)

    if total_paths > 0:
        for path, _ in all_paths:
            for node in path[1:-1]:
                node_centrality[node] += 1.0 / total_paths

    scored_paths = []

    for path, cost in all_paths:
        interior_nodes = path[1:-1]

        if not interior_nodes:
            score = 0.0
        else:
            log_sum = 0.0

            for node in interior_nodes:
                centrality = max(node_centrality.get(node, 0.0), 1e-12)
                log_sum += math.log(centrality)

            score = math.exp(log_sum / len(interior_nodes))

        scored_paths.append((path, cost, score))

    return node_centrality, scored_paths


def collect_k_shortest_base_paths(
    G,
    source,
    targets,
    k=50,
):
    """
    Collect static candidate paths using only base edge cost.

    These candidates are safe to cache because they do not depend on changing
    congestion state. h1/h2/h3 will rescore them later.
    """
    all_paths = []

    def base_edge_weight(u, v, edge_data):
        return edge_data["cost"]

    for target in targets:
        try:
            paths_gen = shortest_simple_paths(
                G,
                source,
                target,
                weight=base_edge_weight,
            )

            for path in itertools.islice(paths_gen, k):
                base_cost = compute_path_base_cost(G, path)

                if math.isfinite(base_cost):
                    all_paths.append((path, base_cost))

        except nx.NetworkXNoPath:
            continue

    return all_paths


def _extract_path_from_candidate(candidate):
    """
    Return the path part from either a raw path or a scored/base candidate.

    Supported inputs:
      - ["A", "B", "C"]
      - (["A", "B", "C"], cost)
      - (["A", "B", "C"], cost, centrality)
    """
    if (
        isinstance(candidate, (list, tuple))
        and candidate
        and isinstance(candidate[0], (list, tuple))
    ):
        return list(candidate[0])

    return list(candidate)


def rescore_candidate_paths(
    G,
    paths,
    *,
    heuristic: str = "none",
    group_size: int = 0,
    horizon_k: int | None = None,
    max_candidates: int | None = None,
    group_id: Any | None = None,
):
    """
    Recompute cached candidate path costs using the active heuristic.

    Candidate paths may arrive either as raw paths or as cached tuples:
      - path
      - (path, base_cost)
      - (path, base_cost, centrality)

    h1/h2/h3 costs depend on current reservation state and must be recomputed at
    each routing decision.
    """
    if max_candidates is not None and max_candidates > 0:
        paths = paths[:max_candidates]

    scored_paths = []

    for candidate in paths:
        path = _extract_path_from_candidate(candidate)

        cost = compute_path_effective_cost(
            G,
            path,
            heuristic=heuristic,
            group_size=group_size,
            horizon_k=horizon_k,
            group_id=group_id,
        )

        scored_paths.append((path, cost))

    scored_paths.sort(key=lambda item: item[1])

    return scored_paths


def compute_efficient_paths(paths, gamma):
    """
    Keep only paths whose cost stays within the gamma tolerance.
    """
    if not paths:
        return []

    finite_paths = [
        path_info
        for path_info in paths
        if math.isfinite(float(path_info[1]))
    ]

    if not finite_paths:
        return []

    min_cost = min(path_info[1] for path_info in finite_paths)
    max_allowed_cost = (1 + gamma) * min_cost

    efficient_paths = [
        path_info
        for path_info in finite_paths
        if path_info[1] <= max_allowed_cost
    ]

    return efficient_paths