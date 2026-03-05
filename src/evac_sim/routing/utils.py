def is_sublist(sub, main) -> bool:
    """
    Check whether `sub` appears as a contiguous slice within `main`.

    Returns:
        bool: True if `sub` is a contiguous sublist of `main`, otherwise False.
    """
    n = len(sub)
    for i in range(len(main) - n + 1):
        if main[i : i + n] == sub:
            return True
    return False


def collect_unblocked_paths(paths, blocked_nodes):
    """
    Filter out paths that contain any blocked node.

    This function implements *soft blocking*: paths containing blocked nodes
    are excluded, but blocking can later be relaxed by higher-level logic.

    Args:
        paths (Iterable[tuple]): Iterable of (path, cost, betweenness).
        blocked_nodes (Iterable): Nodes that must not appear in the path.

    Returns:
        list[tuple]: Filtered list of paths.
    """
    if not blocked_nodes:
        return list(paths)

    blocked_set = set(blocked_nodes)

    return [
        (path, cost, betweenness)
        for path, cost, betweenness in paths
        if not any(node in blocked_set for node in path)
    ]
