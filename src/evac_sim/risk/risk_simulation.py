from __future__ import annotations

import logging
from dataclasses import dataclass
import random
import networkx as nx

from evac_sim.db.repositories.risk import insert_risk_levels

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskStepConfig:
    increase_chance: float
    propagation_threshold: float
    random_increment_min: float = 0.05
    random_increment_max: float = 0.2
    direct_decay: float = 3.0
    second_decay: float = 9.0
    precision: int | None = None


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def maybe_round(x: float, precision: int | None) -> float:
    return round(x, precision) if precision is not None else x


def extract_risks(G: nx.DiGraph) -> dict[str, float]:
    return {node: float(G.nodes[node].get("risk", 0.0)) for node in sorted(G.nodes)}


def apply_risks(G: nx.DiGraph, risks: dict[str, float]) -> None:
    for node, risk in risks.items():
        G.nodes[node]["risk"] = risk


def compute_next_risks(
    G: nx.DiGraph,
    current_risks: dict[str, float],
    cfg: RiskStepConfig,
    rng: random.Random,
) -> dict[str, float]:
    new_risks = dict(current_risks)
    UG = G.to_undirected()

    # 1. Random local increase
    for node in sorted(G.nodes):
        risk = current_risks[node]
        if risk > 0.0 and rng.random() < cfg.increase_chance:
            risk = clamp01(
                risk + rng.uniform(cfg.random_increment_min, cfg.random_increment_max)
            )
        new_risks[node] = maybe_round(risk, cfg.precision)

    # 2. Propagation
    for node in sorted(G.nodes):
        node_risk = current_risks[node]
        if node_risk < cfg.propagation_threshold:
            continue

        first_level = sorted(UG.neighbors(node))
        direct_risk = maybe_round(clamp01(node_risk / cfg.direct_decay), cfg.precision)
        second_risk = maybe_round(clamp01(node_risk / cfg.second_decay), cfg.precision)

        for neighbor in first_level:
            new_risks[neighbor] = max(new_risks[neighbor], direct_risk)

        first_level_set = set(first_level)
        for neighbor in first_level:
            for second_neighbor in sorted(UG.neighbors(neighbor)):
                if second_neighbor == node or second_neighbor in first_level_set:
                    continue
                new_risks[second_neighbor] = max(new_risks[second_neighbor], second_risk)

    return {node: clamp01(risk) for node, risk in new_risks.items()}


def simulate_risk(
    risk_sim_values,
    every_nth_frame: int,
    G: nx.DiGraph,
    exits,
    connection,
    seed: int | None = None,
    case_name: str = "default",
) -> None:
    if risk_sim_values.iterations <= 0:
        raise ValueError("iterations must be a positive integer.")
    if every_nth_frame <= 0:
        raise ValueError("every_nth_frame must be a positive integer.")

    rng = random.Random(seed)

    step_cfg = RiskStepConfig(
        increase_chance=risk_sim_values.increase_chance,
        propagation_threshold=risk_sim_values.propagation_threshold,
        precision=None,
    )

    log.info(
        "Risk simulation start | case=%s iterations=%d every_nth_frame=%d seed=%s",
        case_name,
        risk_sim_values.iterations,
        every_nth_frame,
        seed,
    )

    # Inicialización
    risks = extract_risks(G)

    for node_id, risk_val in risk_sim_values.starting_risks:
        if node_id in risks:
            risks[node_id] = clamp01(float(risk_val))
        else:
            log.warning(
                "Starting risk ignored | case=%s node=%s not found in graph",
                case_name,
                node_id,
            )

    for exit_node in exits:
        if exit_node in risks:
            risks[exit_node] = 0.0
        else:
            log.warning(
                "Exit node ignored while initializing risks | case=%s node=%s not found in graph",
                case_name,
                exit_node,
            )

    apply_risks(G, risks)

    try:
        insert_risk_levels(connection, case_name, 0, risks)
    except Exception:
        log.exception(
            "Failed to persist initial risks | case=%s frame=0",
            case_name,
        )
        raise

    overrides_by_frame: dict[int, list[tuple[str, float]]] = {}
    for frame, node_id, risk_val in risk_sim_values.risk_overrides:
        overrides_by_frame.setdefault(int(frame), []).append((node_id, float(risk_val)))

    for frame in range(1, risk_sim_values.iterations + 1):
        if frame in overrides_by_frame:
            for node_id, risk_val in overrides_by_frame[frame]:
                if node_id in risks:
                    risks[node_id] = clamp01(risk_val)
                else:
                    log.warning(
                        "Risk override ignored | case=%s frame=%d node=%s not found in graph",
                        case_name,
                        frame,
                        node_id,
                    )

        risks = compute_next_risks(G, risks, step_cfg, rng)

        for exit_node in exits:
            if exit_node in risks:
                risks[exit_node] = 0.0

        apply_risks(G, risks)

        if frame % every_nth_frame == 0 or frame == risk_sim_values.iterations:
            try:
                insert_risk_levels(connection, case_name, frame, risks)
            except Exception:
                log.exception(
                    "Failed to persist risks | case=%s frame=%d",
                    case_name,
                    frame,
                )
                raise

    log.info(
        "Risk simulation finished | case=%s last_frame=%d",
        case_name,
        risk_sim_values.iterations,
    )