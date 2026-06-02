from __future__ import annotations

import cProfile
import pstats
from pathlib import Path

from evac_sim.cli import main


PROFILE_DIR = Path("runs/profiling")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_FILE = PROFILE_DIR / "h3_short_vs_wide.prof"
TEXT_REPORT = PROFILE_DIR / "h3_short_vs_wide_top.txt"


def run() -> None:
    main([
        "run",
        "--config",
        "congestion_heuristics.yaml",
        "--case",
        "congestion_short_vs_wide",
        "--heuristic",
        "h3",
        "--beta",
        "1.0",
        "--out-dir",
        "./runs/profile_h3_short_vs_wide_cprofile",
        "-v",
    ])


if __name__ == "__main__":
    profiler = cProfile.Profile()

    profiler.enable()
    run()
    profiler.disable()

    profiler.dump_stats(PROFILE_FILE)

    with TEXT_REPORT.open("w", encoding="utf-8") as f:
        stats = pstats.Stats(profiler, stream=f)
        stats.strip_dirs()
        stats.sort_stats("cumtime")
        stats.print_stats(80)

        f.write("\n\n--- Sorted by total time ---\n\n")
        stats.sort_stats("tottime")
        stats.print_stats(80)

    print(f"Profile saved to: {PROFILE_FILE}")
    print(f"Text report saved to: {TEXT_REPORT}")