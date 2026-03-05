# multifloor_paths.py

from operator import itemgetter

# ──────────────────────────────────────────────────────────────────────────────
# Imports from the project
# ──────────────────────────────────────────────────────────────────────────────
from .path_cache import _get_cached_segments_from_connector, getAlternativePathsForNode

# ──────────────────────────────────────────────────────────────────────────────
# Basic floor / connector helpers
# ──────────────────────────────────────────────────────────────────────────────


def _get_exits_on_floor(EnvInf, exits, floor):
    """Return exits that belong to the given floor."""
    return [e for e in exits if EnvInf.graph.nodes[e]["floor"] == floor]


def _is_connector(EnvInf, node, floor_from, floor_to):
    """Return True if `node` is a connector between `floor_from` and `floor_to`."""
    return node in EnvInf.floor_connecting_nodes.get((floor_from, floor_to), [])


def _segment_end_floor(EnvInf, seg):
    """Return the floor index of the segment's last node."""
    return EnvInf.graph.nodes[seg[-1]]["floor"]


def _get_graph_for_floor(EnvInf, floor: int):
    """Return the floor graph if available; otherwise return the global graph."""
    return EnvInf.floors[floor] if EnvInf.floors is not None else EnvInf.graph


def _build_base_targets(EnvInf, exits, current_floor: int):
    """Return exits on the same floor plus connectors up/down from the current floor."""
    exits_same_floor = _get_exits_on_floor(EnvInf, exits, current_floor)
    targets = list(exits_same_floor)

    if current_floor > 0:
        targets += EnvInf.floor_connecting_nodes.get((current_floor, current_floor - 1), [])
    if current_floor < EnvInf.floor_number - 1:
        targets += EnvInf.floor_connecting_nodes.get((current_floor, current_floor + 1), [])

    return targets


def _vertical_dir_from_last(EnvInf, last_node, current_floor, exits_set):
    """
    Determine vertical movement direction implied by the last node of a segment.

    Returns:
        0 if already at an exit,
        -1 if node connects downward,
        +1 if node connects upward,
        None otherwise.
    """
    if last_node in exits_set:
        return 0
    if current_floor > 0 and _is_connector(EnvInf, last_node, current_floor, current_floor - 1):
        return -1
    if current_floor < EnvInf.floor_number - 1 and _is_connector(
        EnvInf, last_node, current_floor, current_floor + 1
    ):
        return +1
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Multi-floor stitching helpers
# ──────────────────────────────────────────────────────────────────────────────


def _init_complete_and_frontier(EnvInf, alternative_paths, current_floor: int, exits_set):
    """
    Split initial candidate path segments into:
      - complete: segments that already end at an exit
      - frontier: segments that end at a connector (i.e., require multi-floor expansion)

    The frontier keeps additional metadata needed for iterative expansion:
        (segment, cost, betweenness, direction, floor_at_end)

    Args:
        EnvInf: Environment info containing the global graph.
        alternative_paths: Iterable of tuples (segment, cost, betweenness).
        current_floor (int): Floor where the routing starts (kept for API symmetry).
        exits_set (set): Set of exit nodes for fast membership checks.

    Returns:
        tuple:
            complete (list[tuple]): List of (segment, cost, betweenness) that already reach an exit.
            frontier (list[tuple]): List of (segment, cost, betweenness, direction, floor_at_end) to expand further.
    """
    complete = []
    frontier = []  # (seg, cost, betw, dir, floor_at_end)

    for seg, c, b in alternative_paths:
        if not seg:
            continue

        last = seg[-1]
        last_floor = EnvInf.graph.nodes[last]["floor"]

        # Determine whether the segment ends at an exit (0) or at a vertical connector (-1 / +1)
        d = _vertical_dir_from_last(EnvInf, last, last_floor, exits_set)

        if d == 0:
            complete.append((seg, c, b))
        elif d in (-1, +1):
            frontier.append((seg, c, b, d, last_floor))

    return complete, frontier


def _precompute_exits_by_floor(EnvInf, exits):
    """
    Precompute exits grouped by floor to avoid repeated filtering.
    Returns {floor: exits_on_that_floor}.
    """
    return {f: _get_exits_on_floor(EnvInf, exits, f) for f in range(EnvInf.floor_number)}


def _build_targets_for_next_floor(EnvInf, exits_by_floor, next_floor: int, d: int):
    """
    Build routing targets for the next floor during multi-floor expansion.

    Targets include:
      - exits on the next floor
      - connectors that continue moving in the same vertical direction (monotone constraint)
    """
    targets = list(exits_by_floor[next_floor])

    cont_floor = next_floor + d
    if 0 <= cont_floor < EnvInf.floor_number:
        targets += EnvInf.floor_connecting_nodes.get((next_floor, cont_floor), [])

    return targets


def _can_concatenate_without_cycle(seg, seg2):
    """
    Return True if concatenating `seg + seg2[1:]` does not introduce repeated nodes.
    """
    seg_set = set(seg)
    tail = seg2[1:]
    return not any(n in seg_set for n in tail)


def _expand_frontier_once(
    EnvInf,
    frontier,
    exits_set,
    exits_by_floor,
    gamma,
    blocked_nodes,
    visited_states,
):
    """
    Perform one expansion step of the frontier in the multi-floor routing process.

    Returns:
        (complete, new_frontier)
    """
    complete = []
    new_frontier = []

    for seg, c, b, d, floor_at_end in frontier:
        if not seg:
            continue

        connector = seg[-1]

        # Avoid re-expanding the same connector state (helps prevent combinatorial blow-up)
        state = (connector, floor_at_end, d)
        if state in visited_states:
            continue
        visited_states.add(state)

        next_floor = floor_at_end + d
        if next_floor < 0 or next_floor >= EnvInf.floor_number:
            continue

        # Targets on the next floor: exits + monotone-direction connectors
        targets = _build_targets_for_next_floor(EnvInf, exits_by_floor, next_floor, d)

        # Retrieve possible segments from this connector on the next floor (cached if available)
        segments2 = _get_cached_segments_from_connector(
            EnvInf, connector, next_floor, targets, gamma, blocked_nodes
        )

        if not segments2:
            continue

        for seg2, c2, b2 in segments2:
            if not seg2:
                continue
            if not _can_concatenate_without_cycle(seg, seg2):
                continue

            # Concatenate (skip duplicate connector node at seg2[0])
            full = seg + seg2[1:]
            cc = c + c2
            bb = b + b2
            last2 = full[-1]

            # If we reached an exit, store as complete
            if last2 in exits_set:
                complete.append((full, cc, bb))
                continue

            # Otherwise, check if we can keep expanding in the same vertical direction
            last2_floor = EnvInf.graph.nodes[last2]["floor"]
            d2 = _vertical_dir_from_last(EnvInf, last2, last2_floor, exits_set)

            # Enforce monotone vertical direction
            if d2 == d:
                new_frontier.append((full, cc, bb, d, last2_floor))

    return complete, new_frontier


# ──────────────────────────────────────────────────────────────────────────────
# Post-processing helpers (filtering + sorting)
# ──────────────────────────────────────────────────────────────────────────────


def _filter_complete_by_gamma(complete, gamma: float):
    """
    Keep only paths whose cost <= min_cost * (1 + gamma).
    """
    if not complete:
        return complete

    min_cost = min(complete, key=itemgetter(1))[1]
    max_allowed = min_cost * (1 + gamma)

    if any(c > max_allowed for _, c, _ in complete):
        complete = [t for t in complete if t[1] <= max_allowed]

    return complete


def _sort_complete(complete, algo: int):
    """
    Sort complete paths:
      - algo == 0: cost ascending
      - algo == 1: betweenness descending
    """
    complete.sort(
        key=itemgetter(1) if algo == 0 else itemgetter(2),
        reverse=(algo == 1),
    )
    return complete


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def getPosiblePaths(EnvInf, current_node, exits, gamma, algo, *, blocked_nodes=None):
    """
    Compute feasible evacuation paths from `current_node` to any exit, optionally avoiding blocked nodes.

    Steps:
      1) Retrieve in-floor segments to exits and connectors.
      2) Expand segments across floors via connectors while enforcing monotone vertical movement.
      3) Filter complete paths by cost tolerance (gamma).
      4) Sort paths by routing objective (efficient vs centrality).

    Returns:
        list[list]: Paths as lists of nodes.
    """
    if blocked_nodes is None:
        blocked_nodes = []

    exits_set = set(exits)

    current_floor = EnvInf.graph.nodes[current_node]["floor"]
    Gcur = _get_graph_for_floor(EnvInf, current_floor)

    base_targets = _build_base_targets(EnvInf, exits, current_floor)

    alternative_paths = getAlternativePathsForNode(
        current_node,
        base_targets,
        gamma,
        Gcur,
        EnvInf.paths_connection,
        blocked_nodes=blocked_nodes,
    )

    complete, frontier = _init_complete_and_frontier(
        EnvInf, alternative_paths, current_floor, exits_set
    )

    exits_by_floor = _precompute_exits_by_floor(EnvInf, exits)

    visited_states = set()
    while frontier:
        newly_complete, frontier = _expand_frontier_once(
            EnvInf,
            frontier,
            exits_set,
            exits_by_floor,
            gamma,
            blocked_nodes,
            visited_states,
        )
        complete.extend(newly_complete)

    complete = _filter_complete_by_gamma(complete, gamma)
    complete = _sort_complete(complete, algo)

    return [p for p, _, _ in complete]


def getTargetsForCurrentNode(EnvInf, current_node, current_floor, exits):
    """
    Build the list of routing targets available from the current node on the current floor.

    Targets include:
      - exits located on the current floor
      - connectors to the floor below (down)
      - connectors to the floor above (up)
    The current node itself is excluded from connector targets.

    Returns:
        list: Deduplicated list of targets.
    """
    targets = set()

    # Exits on the current floor
    for e in exits:
        if EnvInf.graph.nodes[e]["floor"] == current_floor:
            targets.add(e)

    # Down connectors
    down_floor = current_floor - 1
    if (current_floor, down_floor) in EnvInf.floor_connecting_nodes:
        for n in EnvInf.floor_connecting_nodes[(current_floor, down_floor)]:
            if n != current_node:
                targets.add(n)

    # Up connectors
    up_floor = current_floor + 1
    if (current_floor, up_floor) in EnvInf.floor_connecting_nodes:
        for n in EnvInf.floor_connecting_nodes[(current_floor, up_floor)]:
            for n in EnvInf.floor_connecting_nodes[(current_floor, up_floor)]:
                if n != current_node:
                    targets.add(n)

    return list(targets)
