import json

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Imports from your project
# ──────────────────────────────────────────────────────────────────────────────
from .path_algorithms import collect_k_shortest_paths
from src.evac_sim.db.paths_db_manager import insert_path
from .utils import collect_unblocked_paths

# ──────────────────────────────────────────────────────────────────────────────
# DB-backed path retrieval
# ──────────────────────────────────────────────────────────────────────────────

def getAlternativePathsForNode(
    current_node,
    targets,
    gamma,
    currentG,
    paths_connection,
    *,
    blocked_nodes=None
):
    """
    Retrieve or compute alternative paths from a source node to one or more targets.

    This function attempts to load paths from the DB cache first. If none are found
    for a (source, target) pair, it computes k-shortest paths using the provided graph
    and stores them in the DB for future reuse.

    Note:
        `gamma` is not used directly here, but it is kept in the signature for API
        consistency with higher-level routing components.

    Args:
        current_node: Source node id.
        targets (list | dict_keys): Target node ids.
        gamma (float): Unused here (kept for API consistency).
        currentG: Graph used to compute missing paths.
        paths_connection: SQLite connection used for path caching.
        blocked_nodes (list | None): Nodes that must not appear in the returned paths.

    Returns:
        list[tuple]: List of (path, cost, betweenness) for all targets, filtered by blocked nodes.
    """
    if blocked_nodes is None:
        blocked_nodes = []

    if isinstance(targets, type({}.keys())):
        targets = list(targets)

    all_paths = []

    for target in targets:
        query = "SELECT * FROM paths WHERE source = ? AND target = ?"
        paths_df = pd.read_sql_query(query, paths_connection, params=[current_node, target])

        if not paths_df.empty:
            # Load cached paths
            all_paths.extend(
                [
                    (json.loads(path), cost, betweenness)
                    for path, cost, betweenness in zip(paths_df["path"], paths_df["cost"], paths_df["betweenness"])
                ]
            )
        else:
            # Compute missing paths and persist them
            computed = collect_k_shortest_paths(currentG, current_node, [target])

            for path, cost, betweenness in computed:
                insert_path(paths_connection, current_node, target, cost, path, betweenness)

            all_paths.extend(computed)

    # Remove any path containing blocked nodes (soft constraint)
    all_paths = collect_unblocked_paths(all_paths, blocked_nodes)
    return all_paths


# ──────────────────────────────────────────────────────────────────────────────
# In-memory cache for multi-floor expansion
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_floor_cache(EnvInf, floor: int) -> None:
    """
    Ensure the floor-level cache structure exists.

    Args:
        EnvInf: Environment info containing `floor_paths` dict.
        floor (int): Floor index.

    Returns:
        None
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
    Retrieve cached alternative path segments starting from a connector on `next_floor`.

    NOTE:
        The cache is currently keyed only by (next_floor, connector). If `targets`, `gamma`,
        or `blocked_nodes` vary across calls, cached results may not match the desired constraints.
        If this becomes problematic, enrich the cache key (e.g., include targets hash + blocked hash).

    Args:
        EnvInf: Environment info (graph, optional floors, floor_paths cache, DB connection).
        connector: Connector node id from which we start next-floor routing.
        next_floor (int): Floor index we are expanding into.
        targets (list): Target nodes to compute paths towards.
        gamma (float): Cost tolerance parameter forwarded to getAlternativePathsForNode.
        blocked_nodes (list): Nodes that must not appear in returned segments.

    Returns:
        list[tuple]: List of (segment, cost, betweenness) originating at `connector`.
    """
    _ensure_floor_cache(EnvInf, next_floor)

    if connector not in EnvInf.floor_paths[next_floor]:
        # Choose the appropriate graph view
        Gnext = EnvInf.floors[next_floor] if EnvInf.floors is not None else EnvInf.graph

        EnvInf.floor_paths[next_floor][connector] = getAlternativePathsForNode(
            connector,
            targets,
            gamma,
            Gnext,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes,
        )

    return EnvInf.floor_paths[next_floor].get(connector, [])


def updateFloorPaths(EnvInf, current_floor, sources, targets, gamma, *, blocked_nodes=None) -> None:
    """
    Precompute and cache alternative paths for each source node on a given floor.

    This fills `EnvInf.floor_paths[current_floor]` with:
        { source_node: [(path, cost, betweenness), ...] }

    Args:
        EnvInf: Environment info (includes floors, DB connection, and floor_paths cache).
        current_floor (int): Floor to update.
        sources (list): Source nodes on that floor.
        targets (list): Targets to route towards on that floor.
        gamma (float): API-consistent parameter forwarded to path retrieval.
        blocked_nodes (list | None): Nodes to exclude from paths.

    Returns:
        None
    """
    if blocked_nodes is None:
        blocked_nodes = []

    # Use floor graph if available; otherwise fall back to global graph
    currentG = EnvInf.floors[current_floor] if EnvInf.floors is not None else EnvInf.graph

    all_floor_paths = {}
    for source in sources:
        alternative_paths = getAlternativePathsForNode(
            source,
            targets,
            gamma,
            currentG,
            EnvInf.paths_connection,
            blocked_nodes=blocked_nodes
        )
        all_floor_paths[source] = alternative_paths

    EnvInf.floor_paths[current_floor] = all_floor_paths
