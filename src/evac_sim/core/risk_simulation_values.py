from dataclasses import dataclass, field

StartingRisk = tuple[str, float]
RiskOverride = tuple[int, str, float]


@dataclass(slots=True)
class RiskSimulationValues:
    """
    Configuration parameters controlling the risk simulation.

    Attributes
    ----------
    iterations:
        Total number of simulation frames.

    increase_chance:
        Probability of an individual risk increase per frame.

    propagation_threshold:
        Risk value above which a node becomes an active emitter and
        propagates risk to neighbouring nodes.

    starting_risks:
        Initial risk values assigned to specific nodes as
        `(node_id, risk_value)` tuples.

    risk_overrides:
        Forced risk assignments applied at specific frames as
        `(frame, node_id, risk_value)` tuples.
    """

    iterations: int = 3000
    increase_chance: float = 0.01
    propagation_threshold: float = 0.5
    starting_risks: list[StartingRisk] = field(default_factory=list)
    risk_overrides: list[RiskOverride] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.iterations <= 0:
            raise ValueError("iterations must be > 0")
        if not 0 <= self.increase_chance <= 1:
            raise ValueError("increase_chance must be between 0 and 1")
        if not 0 <= self.propagation_threshold <= 1:
            raise ValueError("propagation_threshold must be between 0 and 1")