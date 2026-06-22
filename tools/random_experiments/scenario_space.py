from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioSpec:
    key: str
    template_case_id: str
    environment: str
    possible_sources: list[str]
    possible_targets: list[str]


def _range_as_strings(
    start: int,
    end: int,
    *,
    excluded: set[int] | None = None,
) -> list[str]:
    excluded = excluded or set()

    return [
        str(value)
        for value in range(start, end + 1)
        if value not in excluded
    ]


SCENARIOS: dict[str, ScenarioSpec] = {
    "two_corridors": ScenarioSpec(
        key="two_corridors",
        template_case_id="congestion_parallel_corridors",
        environment="parallel_corridors",
        possible_sources=["9", "19", "1", "10", "2"],
        possible_targets=["24", "25", "23", "22", "18", "17"],
    ),

    "short_vs_wide": ScenarioSpec(
        key="short_vs_wide",
        template_case_id="congestion_short_vs_wide",
        environment="short_vs_wide",
        possible_sources=["1", "26", "27", "28", "3", "32", "33", "34"],
        possible_targets=["2", "29", "30", "31", "4", "35", "36", "37"],
    ),

    "two_exits": ScenarioSpec(
        key="two_exits",
        template_case_id="congestion_two_exits",
        environment="two_exits",
        possible_sources=_range_as_strings(
            1,
            54,
            excluded={13, 14, 15, 16, 17, 18},
        ),
        possible_targets=[
            "17", "63", "64", "65", "18", "66",
            "58", "59", "60", "61", "62",
        ],
    ),
}


EFFICIENT_HIGH_MODE_TYPE = 5
DEFAULT_HEURISTICS = ["none", "h1", "h2", "h3"]