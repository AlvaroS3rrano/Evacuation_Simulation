from __future__ import annotations

import math

from evac_sim.db.repositories.path_cache import get_paths, upsert_path

from .path_algorithms import (
    centrality_measures,
    collect_k_shortest_base_paths,
    compute_efficient_paths,
    rescore_candidate_paths,
)
from .utils import collect_unblocked_paths


# Number of static base-cost paths to compute/cache per source-target pair.
# Dynamic heuristics keep a wider cached pool because congestion can make a
# slightly longer base path preferable.
STATIC_CANDIDATE_K_NONE = 15
STATIC_CANDIDATE_K_DYNAMIC = 50

# Number of cached candidates that are dynamically rescored on each routing
# decision. This is intentionally lower than STATIC_CANDIDATE_K_DYNAMIC because
# h1/h2/h3 costs are recomputed very frequently during simulation.
SCORED_CANDIDATE_LIMIT_NONE = 15

SCORED_CANDIDATE_LIMIT_BY_HEURISTIC = {
    "h1": 15,
    "h2": 20,
    "h3": 30,
}

DYNAMIC_HEURISTICS = {"h1", "h2", "h3"}


def _sort_paths(paths):
    return sorted(
        paths,
        key=lambda t: (
            float(t[1]),     # cost
            -float(t[2]),    # centrality
            tuple(t[0]),
        ),
    )


def _candidate_pool_size(heuristic: str) -> int:
    if heuristic in DYNAMIC_HEURISTICS:
        return STATIC_CANDIDATE_K_DYNAMIC

    return STATIC_CANDIDATE_K_NONE


def _scored_candidate_limit(heuristic: str) -> int:
    return SCORED_CANDIDATE_LIMIT_BY_HEURISTIC.get(
        heuristic,
        SCORED_CANDIDATE_LIMIT_NONE,
    )


def _graph_candidate_cache(currentG) -> dict:
    """
    Return the in-memory candidate path cache attached to the graph.

    This avoids recomputing shortest_simple_paths for h1/h2/h3 while avoiding
    cross-environment contamination from the persistent DB cache.
    """
    return currentG.graph.setdefault("candidate_path_cache", {})


def _candidate_cache_key(source, target, k: int) -> tuple[str, str, int]:
    return str(source), str(target), int(k)


def _normalise_cached_paths(paths):
    """
    Store cached paths as tuples internally to avoid accidental mutation.
    Return list-based paths to keep compatibility with existing code.
    """
    return [
        (list(path), float(cost))
        for path, cost in paths
    ]


def _store_cached_paths(paths):
    return tuple(
        (tuple(path), float(cost))
        for path, cost in paths
    )


def _get_or_compute_base_candidate_paths(
    *,
    currentG,
    paths_connection,
    source,
    target,
    candidate_k: int,
    use_persistent_cache: bool,
):
    """
    Get static base-cost candidate paths for a source-target pair.

    These candidates are independent from congestion state, so they can be reused
    by none/h1/h2/h3. Dynamic heuristics rescore the returned paths afterwards.
    """
    memory_cache = _graph_candidate_cache(currentG)
    cache_key = _candidate_cache_key(source, target, candidate_k)

    if cache_key in memory_cache:
        return _normalise_cached_paths(memory_cache[cache_key])

    db_paths = []

    if use_persistent_cache:
        db_paths = get_paths(paths_connection, source, target)

        if len(db_paths) >= candidate_k:
            base_paths = [
                (p["path"], p["cost"])
                for p in db_paths[:candidate_k]
            ]
            memory_cache[cache_key] = _store_cached_paths(base_paths)
            return base_paths

    computed = collect_k_shortest_base_paths(
        currentG,
        source,
        [target],
        k=candidate_k,
    )

    computed = sorted(
        computed,
        key=lambda t: (float(t[1]), tuple(t[0])),
    )

    if use_persistent_cache:
        for path, cost in computed:
            upsert_path(paths_connection, source, target, cost, path)

    if not computed and db_paths:
        computed = [
            (p["path"], p["cost"])
            for p in db_paths[:candidate_k]
        ]

    memory_cache[cache_key] = _store_cached_paths(computed)

    return _normalise_cached_paths(memory_cache[cache_key])


def _prepare_candidates_for_scoring(
    base_candidates,
    *,
    blocked_nodes=None,
    apply_block_filter=True,
    score_limit: int,
):
    """
    Prepare the cached base candidates before dynamic scoring.

    Block filtering can be safely applied before h1/h2/h3 scoring because it
    depends only on the path nodes, not on dynamic congestion cost.
    """
    candidates = base_candidates

    if apply_block_filter and blocked_nodes:
        candidates = collect_unblocked_paths(candidates, blocked_nodes)

    if score_limit is not None and score_limit > 0:
        candidates = candidates[:score_limit]

    return candidates

def _filter_finite_cost_paths(paths):
    return [
        path_tuple
        for path_tuple in paths
        if len(path_tuple) > 1 and math.isfinite(float(path_tuple[1]))
    ]

def process_candidate_paths(paths, *, blocked_nodes=None, gamma=None, G=None):
    if blocked_nodes:
        paths = collect_unblocked_paths(paths, blocked_nodes)

    if gamma is not None:
        paths = compute_efficient_paths(paths, gamma)

    _, paths = centrality_measures(G, paths)

    return _sort_paths(paths)


def get_alternative_paths_for_node(
    current_node,
    targets,
    gamma,
    currentG,
    paths_connection,
    *,
    blocked_nodes=None,
    apply_block_filter=True,
    apply_gamma_filter=True,
    heuristic="none",
    group_size=0,
    group_id=None,
    horizon_k=None,
):
    if blocked_nodes is None:
        blocked_nodes = []

    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    all_paths = []

    candidate_k = _candidate_pool_size(heuristic)
    score_limit = _scored_candidate_limit(heuristic)

    # Persistent cache stores only static base-cost paths.
    # Dynamic heuristic costs are never persisted because they depend on current
    # occupancy and temporal reservations.
    use_persistent_cache = True

    # We pre-apply the block filter before dynamic scoring to avoid scoring
    # candidates that will be discarded anyway.
    block_filter_applied_before_scoring = bool(
        apply_block_filter and blocked_nodes
    )

    for target in targets:
        base_candidates = _get_or_compute_base_candidate_paths(
            currentG=currentG,
            paths_connection=paths_connection,
            source=current_node,
            target=target,
            candidate_k=candidate_k,
            use_persistent_cache=use_persistent_cache,
        )

        candidates_to_score = _prepare_candidates_for_scoring(
            base_candidates,
            blocked_nodes=blocked_nodes,
            apply_block_filter=apply_block_filter,
            score_limit=score_limit,
        )

        scored_candidates = rescore_candidate_paths(
            currentG,
            candidates_to_score,
            heuristic=heuristic,
            group_size=group_size,
            horizon_k=horizon_k,
            max_candidates=_scored_candidate_limit(heuristic),
            group_id=group_id,
        )

        scored_candidates = _filter_finite_cost_paths(scored_candidates)

        all_paths.extend(scored_candidates)

    return process_candidate_paths(
        all_paths,
        blocked_nodes=(
            None
            if block_filter_applied_before_scoring
            else blocked_nodes if apply_block_filter else None
        ),
        gamma=gamma if apply_gamma_filter else None,
        G=currentG,
    )


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
    heuristic="none",
    group_size=0,
    group_id=None,
    horizon_k=None,
):
    """
    Retrieve path segments from a connector on the next floor.

    Final path lists are cached only for heuristic none. Dynamic heuristics keep
    using get_alternative_paths_for_node so costs are rescored from the current
    congestion state, but the base candidate path pool is still cached in memory.
    """
    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    use_floor_cache = heuristic == "none"

    Gnext = EnvInf.floors[next_floor] if EnvInf.floors is not None else EnvInf.graph

    if not use_floor_cache:
        return get_alternative_paths_for_node(
            connector,
            targets,
            gamma,
            Gnext,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
            apply_block_filter=True,
            apply_gamma_filter=False,
            heuristic=heuristic,
            group_size=group_size,
            group_id=group_id,
            horizon_k=horizon_k,
        )

    _ensure_floor_cache(EnvInf, next_floor)

    targets_key = tuple(sorted(targets))
    blocked_key = tuple(sorted(blocked_nodes or []))
    gamma_key = round(float(gamma), 12) if gamma is not None else None

    cache_key = (connector, targets_key, gamma_key, blocked_key)

    if cache_key not in EnvInf.floor_paths[next_floor]:
        EnvInf.floor_paths[next_floor][cache_key] = get_alternative_paths_for_node(
            connector,
            targets,
            gamma,
            Gnext,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
            apply_block_filter=True,
            apply_gamma_filter=False,
            heuristic=heuristic,
            group_size=group_size,
            group_id=group_id,
            horizon_k=horizon_k,
        )

    return EnvInf.floor_paths[next_floor].get(cache_key, [])


def updateFloorPaths(
    EnvInf,
    current_floor,
    sources,
    targets,
    gamma,
    *,
    blocked_nodes=None,
    heuristic="none",
    group_size=0,
    group_id=None,
    horizon_k=None,
) -> None:
    """
    Precompute and cache alternative paths for each source node on a floor.
    """
    if blocked_nodes is None:
        blocked_nodes = []

    currentG = EnvInf.floors[current_floor] if EnvInf.floors is not None else EnvInf.graph

    all_floor_paths = {}
    for source in sources:
        alternative_paths = get_alternative_paths_for_node(
            source,
            targets,
            gamma,
            currentG,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
            heuristic=heuristic,
            group_size=group_size,
            group_id=group_id,
            horizon_k=horizon_k,
        )
        all_floor_paths[source] = alternative_paths

    EnvInf.floor_paths[current_floor] = all_floor_paths