import itertools
import logging
import math

import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths

from evac_sim.routing.heuristics import compute_effective_step_cost
from evac_sim.simulation.temporal_capacity import compute_temporal_path_effective_cost


logger = logging.getLogger(__name__)


def _get_projected_group_size_for_step(
    *,
    edge_index: int,
    heuristic: str,
    group_size: int,
    horizon_k: int | None,
) -> int:
    """
    Return the group size projected onto one static path step.

    h1 projects the group over the whole remaining path.
    h2 projects the group only over the first horizon_k steps.
    h3 is evaluated separately by temporal path scoring.
    """
    if heuristic == "h2":
        if horizon_k is None:
            raise ValueError("horizon_k must be provided when heuristic='h2'")

        if edge_index >= horizon_k:
            return 0

    return group_size


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
    beta: float = 1.0,
    group_size: int = 0,
    horizon_k: int | None = None,
) -> float:
    """
    Compute the effective cost of a complete path.

    This function is the single source of truth for path cost computation.

    For h1:
        The current group is projected over every edge in the path.

    For h2:
        The current group is projected only over the first horizon_k edges.
        Steps beyond the horizon still include existing flow/node occupancy, but the
        current group is not projected onto them.

    For h3:
        The path is evaluated with temporal node/edge capacity by estimated
        arrival bucket.

    For none:
        The base edge cost is used.
    """
    if not path or len(path) < 2:
        return float("inf")

    if heuristic == "h3":
        return compute_temporal_path_effective_cost(
            G,
            path,
            group_size=group_size,
            beta=beta,
        )

    if heuristic == "none":
        return sum(
            float(G[u][v]["cost"])
            for u, v in zip(path, path[1:])
        )

    total = 0.0

    if heuristic == "h1":
        for u, v in zip(path, path[1:]):
            total += compute_effective_step_cost(
                edge_data=G[u][v],
                target_node_data=G.nodes[v],
                heuristic=heuristic,
                beta=beta,
                group_size=group_size,
            )

        return total

    if heuristic == "h2":
        if horizon_k is None:
            raise ValueError("horizon_k must be provided when heuristic='h2'")

        for edge_index, (u, v) in enumerate(zip(path, path[1:])):
            if edge_index >= horizon_k:
                total += float(G[u][v]["cost"])
                continue

            total += compute_effective_step_cost(
                edge_data=G[u][v],
                target_node_data=G.nodes[v],
                heuristic=heuristic,
                beta=beta,
                group_size=group_size,
            )

        return total

    raise ValueError(f"Unknown heuristic: {heuristic}")


def centrality_measures(G, all_paths):
    """
    Compute node centrality over a candidate path set and assign each path
    a geometric-mean score based on its interior nodes.
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
                c = max(node_centrality.get(node, 0.0), 1e-12)
                log_sum += math.log(c)

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
    beta: float = 1.0,
    group_size: int = 0,
    horizon_k: int | None = None,
    max_candidates: int | None = None,
):
    """
    Recompute cached candidate path costs using the active heuristic.

    Candidate paths may arrive either as raw paths or as cached tuples:
      - path
      - (path, base_cost)
      - (path, base_cost, centrality)

    h1/h2/h3 costs depend on current congestion state and must be recomputed at
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
            beta=beta,
            group_size=group_size,
            horizon_k=horizon_k,
        )

        scored_paths.append((path, cost))

    scored_paths.sort(key=lambda item: item[1])

    return scored_paths


def collect_k_shortest_paths(
    G,
    source,
    targets,
    k=15,
    heuristic="none",
    beta=1.0,
    group_size=0,
    horizon_k=None,
):
    """
    Backwards-compatible wrapper.

    Candidate generation is now static and cache-friendly. Dynamic heuristics
    rescore the candidate pool using the current graph state.
    """
    candidate_paths = collect_k_shortest_base_paths(
        G,
        source,
        targets,
        k=k,
    )

    return rescore_candidate_paths(
        G,
        candidate_paths,
        heuristic=heuristic,
        beta=beta,
        group_size=group_size,
        horizon_k=horizon_k,
    )


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