from evac_sim.db.repositories.path_cache import upsert_path, get_paths

from .path_algorithms import (
    centrality_measures,
    collect_k_shortest_paths,
    compute_efficient_paths,
)
from .utils import collect_unblocked_paths


def _sort_paths(paths):
    return sorted(
        paths,
        key=lambda t: (
            float(t[1]),     # cost
            -float(t[2]),    # centrality
            tuple(t[0]),
        ),
    )


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
    beta=1.0,
    group_size=0,
):
    if blocked_nodes is None:
        blocked_nodes = []

    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    all_paths = []

    use_db_cache = heuristic == "none"

    for target in targets:
        if use_db_cache:
            paths = get_paths(paths_connection, current_node, target)
        else:
            paths = None

        if paths:
            all_paths.extend(
                [(p["path"], p["cost"]) for p in paths]
            )
        else:
            computed = collect_k_shortest_paths(
                currentG,
                current_node,
                [target],
                heuristic=heuristic,
                beta=beta,
                group_size=group_size,
            )

            computed = sorted(
                computed,
                key=lambda t: (float(t[1]), tuple(t[0])),
            )

            if use_db_cache:
                for path, cost in computed:
                    upsert_path(paths_connection, current_node, target, cost, path)

            all_paths.extend(computed)

    return process_candidate_paths(
        all_paths,
        blocked_nodes=blocked_nodes if apply_block_filter else None,
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
    beta=1.0,
    group_size=0,
):
    """
    Retrieve cached path segments from a connector on the next floor.
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
            beta=beta,
            group_size=group_size,
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
            beta=beta,
            group_size=group_size,
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
    beta=1.0,
    group_size=0,
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
            beta=beta,
            group_size=group_size,
        )
        all_floor_paths[source] = alternative_paths

    EnvInf.floor_paths[current_floor] = all_floor_paths