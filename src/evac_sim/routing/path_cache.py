import json

import pandas as pd

from evac_sim.db.repositories.path_cache import upsert_path

from .path_algorithms import centrality_measures, collect_k_shortest_paths
from .utils import collect_unblocked_paths


def _rescore_paths_for_current_candidate_set(currentG, paths):
    """
    Recompute path scores on the current candidate set.
    """
    if not paths:
        return []

    raw_paths = [(path, cost) for path, cost, _ in paths]
    _, rescored_paths = centrality_measures(currentG, raw_paths)

    return sorted(
        rescored_paths,
        key=lambda t: (
            float(t[1]),
            -float(t[2]),
            tuple(t[0]),
        ),
    )


def getAlternativePathsForNode(
    current_node, targets, gamma, currentG, paths_connection, *, blocked_nodes=None
):
    """
    Retrieve or compute alternative paths from a source node to one or more targets.
    """
    if blocked_nodes is None:
        blocked_nodes = []

    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    all_paths = []

    for target in targets:
        query = (
            "SELECT path, cost, betweenness "
            "FROM paths "
            "WHERE source = ? AND target = ? "
            "ORDER BY cost ASC, betweenness DESC, path ASC"
        )
        paths_df = pd.read_sql_query(query, paths_connection, params=[current_node, target])

        if not paths_df.empty:
            all_paths.extend(
                [
                    (json.loads(path), cost, betweenness)
                    for path, cost, betweenness in zip(
                        paths_df["path"], paths_df["cost"], paths_df["betweenness"]
                    )
                ]
            )
        else:
            computed = collect_k_shortest_paths(currentG, current_node, [target])

            computed = sorted(
                computed,
                key=lambda t: (
                    float(t[1]),
                    -float(t[2]),
                    tuple(t[0]),
                ),
            )

            for path, cost, betweenness in computed:
                upsert_path(paths_connection, current_node, target, cost, path, betweenness)

            all_paths.extend(computed)

    all_paths = collect_unblocked_paths(all_paths, blocked_nodes)

    return _rescore_paths_for_current_candidate_set(currentG, all_paths)


def _ensure_floor_cache(EnvInf, floor: int) -> None:
    """
    Ensure the floor-level cache structure exists.
    """
    if floor not in EnvInf.floor_paths:
        EnvInf.floor_paths[floor] = {}


def _get_cached_segments_from_connector(
    EnvInf,
    connector,
    next_floor: int,
    targets,
    gamma,
    blocked_nodes,
):
    """
    Retrieve cached path segments from a connector on the next floor.
    """
    _ensure_floor_cache(EnvInf, next_floor)

    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    targets_key = tuple(sorted(targets))
    blocked_key = tuple(sorted(blocked_nodes or []))
    gamma_key = round(float(gamma), 12) if gamma is not None else None

    cache_key = (connector, targets_key, gamma_key, blocked_key)

    if cache_key not in EnvInf.floor_paths[next_floor]:
        Gnext = EnvInf.floors[next_floor] if EnvInf.floors is not None else EnvInf.graph

        EnvInf.floor_paths[next_floor][cache_key] = getAlternativePathsForNode(
            connector,
            targets,
            gamma,
            Gnext,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
        )

    return EnvInf.floor_paths[next_floor].get(cache_key, [])


def updateFloorPaths(EnvInf, current_floor, sources, targets, gamma, *, blocked_nodes=None) -> None:
    """
    Precompute and cache alternative paths for each source node on a floor.
    """
    if blocked_nodes is None:
        blocked_nodes = []

    currentG = EnvInf.floors[current_floor] if EnvInf.floors is not None else EnvInf.graph

    all_floor_paths = {}
    for source in sources:
        alternative_paths = getAlternativePathsForNode(
            source,
            targets,
            gamma,
            currentG,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
        )
        all_floor_paths[source] = alternative_paths

    EnvInf.floor_paths[current_floor] = all_floor_paths