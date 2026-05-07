import itertools
import math

import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths

from evac_sim.routing.heuristics import compute_effective_edge_cost

import logging

logger = logging.getLogger(__name__)

def _get_projected_group_size_for_edge(
    *,
    edge_index: int,
    heuristic: str,
    group_size: int,
    horizon_k: int | None,
) -> int:
    """
    Return the projected group size that should be applied to an edge.

    h1:
        The group is projected over the whole path.

    h2:
        The group is projected only over the first horizon_k edges.

    none:
        The value does not matter because compute_effective_edge_cost ignores
        group_size when heuristic == "none".
    """
    if heuristic == "h2":
        if horizon_k is None:
            raise ValueError("horizon_k must be provided when heuristic='h2'")

        if edge_index >= horizon_k:
            return 0

    return group_size


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
        Edges beyond the horizon still include their current occupancy, but
        the current group is not added to them.

    For none:
        The base edge cost is used.
    """
    if not path or len(path) < 2:
        return float("inf")

    total = 0.0

    for edge_index, (u, v) in enumerate(zip(path, path[1:])):
        projected_group_size = _get_projected_group_size_for_edge(
            edge_index=edge_index,
            heuristic=heuristic,
            group_size=group_size,
            horizon_k=horizon_k,
        )

        total += compute_effective_edge_cost(
            edge_data=G[u][v],
            heuristic=heuristic,
            beta=beta,
            group_size=projected_group_size,
        )

    return total

def centrality_measures(G, all_paths):
    """
    Compute node centrality over a candidate path set and assign each path
    a geometric-mean score based on its interior nodes.

    Args:
        G (nx.DiGraph): Directed graph.
        all_paths (list[tuple]): List of (path, cost) tuples.

    Returns:
        tuple:
            node_centrality (dict): Relative frequency of each node as an
                interior node in the candidate path set.
            scored_paths (list): List of (path, cost, score) tuples.
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
    all_paths = []

    def edge_weight(u, v, edge_data):
        if heuristic == "h2":
            return compute_effective_edge_cost(
                edge_data=edge_data,
                heuristic=heuristic,
                beta=beta,
                group_size=0,
            )

        return compute_effective_edge_cost(
            edge_data=edge_data,
            heuristic=heuristic,
            beta=beta,
            group_size=group_size,
        )

    for target in targets:
        try:
            paths_gen = shortest_simple_paths(
                G,
                source,
                target,
                weight=edge_weight,
            )

            for path in itertools.islice(paths_gen, k):
                cost = compute_path_effective_cost(
                    G,
                    path,
                    heuristic=heuristic,
                    beta=beta,
                    group_size=group_size,
                    horizon_k=horizon_k,
                )

                all_paths.append((path, cost))

                logger.info(
                    "Candidate path | source=%s target=%s heuristic=%s beta=%.2f group_size=%s horizon_k=%s path=%s cost=%.3f",
                    source,
                    target,
                    heuristic,
                    beta,
                    group_size,
                    horizon_k,
                    path,
                    cost,
                )

        except nx.NetworkXNoPath:
            continue

    return all_paths

def compute_efficient_paths(paths, gamma):
    """
    Keep only paths whose cost stays within the gamma tolerance.
    """
    if not paths:
        return []

    min_cost = min(path[1] for path in paths)
    max_allowed_cost = (1 + gamma) * min_cost

    efficient_paths = [
        (path, cost, centrality)
        for path, cost, centrality in paths
        if cost <= max_allowed_cost
    ]

    return efficient_paths