from operator import itemgetter

from .path_algorithms import centrality_measures
from .path_cache import _get_cached_segments_from_connector, getAlternativePathsForNode


def _get_exits_on_floor(EnvInf, exits, floor):
    """Return exits that belong to the given floor."""
    return [e for e in exits if EnvInf.graph.nodes[e]["floor"] == floor]


def _is_connector(EnvInf, node, floor_from, floor_to):
    """Return True if node connects two floors."""
    return node in EnvInf.floor_connecting_nodes.get((floor_from, floor_to), [])


def _segment_end_floor(EnvInf, seg):
    """Return the floor index of the segment's last node."""
    return EnvInf.graph.nodes[seg[-1]]["floor"]


def _get_graph_for_floor(EnvInf, floor: int):
    """Return the graph for a floor or the global graph."""
    return EnvInf.floors[floor] if EnvInf.floors is not None else EnvInf.graph


def _build_base_targets(EnvInf, exits, current_floor: int):
    """Return same-floor exits and adjacent-floor connectors."""
    exits_same_floor = _get_exits_on_floor(EnvInf, exits, current_floor)
    targets = list(exits_same_floor)

    if current_floor > 0:
        targets += EnvInf.floor_connecting_nodes.get((current_floor, current_floor - 1), [])
    if current_floor < EnvInf.floor_number - 1:
        targets += EnvInf.floor_connecting_nodes.get((current_floor, current_floor + 1), [])

    return targets


def _vertical_dir_from_last(EnvInf, last_node, current_floor, exits_set):
    """
    Return the vertical direction implied by the last node.
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


def _init_complete_and_frontier(EnvInf, alternative_paths, current_floor: int, exits_set):
    """
    Split initial paths into complete paths and expandable frontier states.
    """
    complete = []
    frontier = []  # (segment, cost, direction, floor_at_end)

    for seg, c, _ in alternative_paths:
        if not seg:
            continue

        last = seg[-1]
        last_floor = EnvInf.graph.nodes[last]["floor"]
        d = _vertical_dir_from_last(EnvInf, last, last_floor, exits_set)

        if d == 0:
            complete.append((seg, c))
        elif d in (-1, +1):
            frontier.append((seg, c, d, last_floor))

    return complete, frontier


def _precompute_exits_by_floor(EnvInf, exits):
    """
    Group exits by floor.
    """
    return {f: _get_exits_on_floor(EnvInf, exits, f) for f in range(EnvInf.floor_number)}


def _build_targets_for_next_floor(EnvInf, exits_by_floor, next_floor: int, d: int):
    """
    Build targets for the next floor during expansion.
    """
    targets = list(exits_by_floor[next_floor])

    cont_floor = next_floor + d
    if 0 <= cont_floor < EnvInf.floor_number:
        targets += EnvInf.floor_connecting_nodes.get((next_floor, cont_floor), [])

    return targets


def _can_concatenate_without_cycle(seg, seg2):
    """
    Return True if seg + seg2[1:] does not repeat nodes.
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
    Expand one step of the multi-floor frontier.
    """
    complete = []
    new_frontier = []

    for seg, c, d, floor_at_end in frontier:
        if not seg:
            continue

        connector = seg[-1]
        state = (connector, floor_at_end, d)
        if state in visited_states:
            continue
        visited_states.add(state)

        next_floor = floor_at_end + d
        if next_floor < 0 or next_floor >= EnvInf.floor_number:
            continue

        targets = _build_targets_for_next_floor(EnvInf, exits_by_floor, next_floor, d)

        segments2 = _get_cached_segments_from_connector(
            EnvInf, connector, next_floor, targets, gamma, blocked_nodes
        )

        if not segments2:
            continue

        for seg2, c2, _ in segments2:
            if not seg2:
                continue
            if not _can_concatenate_without_cycle(seg, seg2):
                continue

            full = seg + seg2[1:]
            cc = c + c2
            last2 = full[-1]

            if last2 in exits_set:
                complete.append((full, cc))
                continue

            last2_floor = EnvInf.graph.nodes[last2]["floor"]
            d2 = _vertical_dir_from_last(EnvInf, last2, last2_floor, exits_set)

            if d2 == d:
                new_frontier.append((full, cc, d, last2_floor))

    return complete, new_frontier


def _filter_complete_by_gamma(complete, gamma: float):
    """
    Keep only paths within the gamma cost tolerance.
    """
    if not complete:
        return complete

    min_cost = min(complete, key=itemgetter(1))[1]
    max_allowed = min_cost * (1 + gamma)

    if any(c > max_allowed for _, c in complete):
        complete = [t for t in complete if t[1] <= max_allowed]

    return complete


def _rescore_complete_paths(EnvInf, complete):
    """
    Recompute centrality scores on the final candidate path set.
    """
    if not complete:
        return []

    _, rescored = centrality_measures(EnvInf.graph, complete)
    return rescored


def _sort_complete(complete, algo: int):
    """
    Sort complete paths by the active routing objective.
    """
    if algo == 0:
        complete.sort(key=lambda t: (float(t[1]), tuple(t[0])))
    else:
        complete.sort(key=lambda t: (-float(t[2]), float(t[1]), tuple(t[0])))

    return complete


def getPosiblePaths(EnvInf, current_node, exits, gamma, algo, *, blocked_nodes=None):
    """
    Compute feasible paths from the current node to any exit.
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
    complete = _rescore_complete_paths(EnvInf, complete)
    complete = _sort_complete(complete, algo)

    return [p for p, _, _ in complete]


def getTargetsForCurrentNode(EnvInf, current_node, current_floor, exits):
    """
    Build the list of routing targets on the current floor.
    """
    targets = set()

    for e in exits:
        if EnvInf.graph.nodes[e]["floor"] == current_floor:
            targets.add(e)

    down_floor = current_floor - 1
    if (current_floor, down_floor) in EnvInf.floor_connecting_nodes:
        for n in EnvInf.floor_connecting_nodes[(current_floor, down_floor)]:
            if n != current_node:
                targets.add(n)

    up_floor = current_floor + 1
    if (current_floor, up_floor) in EnvInf.floor_connecting_nodes:
        for n in EnvInf.floor_connecting_nodes[(current_floor, up_floor)]:
            if n != current_node:
                targets.add(n)

    return list(targets)