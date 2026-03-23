import itertools
import math

import networkx as nx
from networkx.algorithms.simple_paths import shortest_simple_paths


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


def collect_k_shortest_paths(G: nx.DiGraph, source, targets, k=15):
    """
    Collect up to k simple minimum-cost paths from the source to each target
    and score them using the current candidate path set.

    Args:
        G (nx.DiGraph): Directed graph where edges have a 'cost' attribute.
        source: Source node.
        targets (list): Target nodes.
        k (int): Maximum number of shortest simple paths per target.

    Returns:
        list: A list of (path, cost, centrality_score) tuples.
    """
    all_paths = []

    for target in targets:
        try:
            paths_gen = shortest_simple_paths(G, source, target, weight="cost")

            for path in itertools.islice(paths_gen, k):
                cost = sum(G[u][v]["cost"] for u, v in zip(path, path[1:]))
                all_paths.append((path, cost))

        except nx.NetworkXNoPath:
            continue

    _, scored_paths = centrality_measures(G, all_paths)
    return scored_paths


def collect_unblocked_paths(paths, blocked_nodes):
    """
    Filter out paths that contain blocked nodes.
    """
    if blocked_nodes:
        paths = [
            (path, cost, centrality)
            for (path, cost, centrality) in paths
            if not any(node in blocked_nodes for node in path)
        ]
    return paths


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