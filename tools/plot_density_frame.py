from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evac_sim.envs.environment_factory import select_environment  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a density image using the same area_density definition "
            "used by derived congestion metrics."
        )
    )

    parser.add_argument(
        "--db",
        required=True,
        help="Path to simulation.db.",
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Config YAML filename inside configs/ or an absolute path.",
    )

    parser.add_argument(
        "--case",
        required=True,
        help="Case id inside the YAML config.",
    )

    parser.add_argument(
        "--frame",
        type=int,
        default=None,
        help=(
            "Frame to plot. If omitted, the frame with the highest area density "
            "is selected."
        ),
    )

    parser.add_argument(
        "--sample-every-frames",
        type=int,
        default=1,
        help=(
            "Optional frame sampling interval. Use the same value as metrics "
            "density config."
        ),
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Output PNG path. Defaults to artifacts/img/density_frame_<frame>.png "
            "next to the db."
        ),
    )

    return parser.parse_args()


def load_case_config(config_name: str, case_id: str) -> dict[str, Any]:
    config_path = Path(config_name)

    if not config_path.exists():
        config_path = PROJECT_ROOT / "configs" / config_name

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_name}")

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if case_id not in data:
        raise KeyError(f"Case {case_id!r} not found in {config_path}")

    case_cfg = data[case_id]

    if not isinstance(case_cfg, dict):
        raise TypeError(f"Case {case_id!r} must be a mapping")

    return case_cfg


def _as_polygon(geometry_like: Any) -> Any:
    """
    Return a Shapely-like polygon from either:
      - a Shapely Polygon
      - a PedPy WalkableArea-like object exposing .polygon
    """
    return getattr(geometry_like, "polygon", geometry_like)


def _iter_polygons(geometry_like: Any) -> list[Any]:
    """
    Return a list of Shapely-like polygons.

    Supports simple Polygon, MultiPolygon, and PedPy WalkableArea-like objects.
    """
    polygon = _as_polygon(geometry_like)

    if hasattr(polygon, "geoms"):
        return list(polygon.geoms)

    return [polygon]


def _plot_polygon_boundaries(ax, geometry_like: Any, *, linewidth: float = 1.0) -> None:
    for polygon in _iter_polygons(geometry_like):
        if not hasattr(polygon, "exterior"):
            continue

        exterior_x, exterior_y = polygon.exterior.xy
        ax.plot(exterior_x, exterior_y, linewidth=linewidth)

        for interior in getattr(polygon, "interiors", []):
            interior_x, interior_y = interior.xy
            ax.plot(interior_x, interior_y, linewidth=linewidth)


def load_density_by_area_frame(
    db_path: Path,
    *,
    sample_every_frames: int,
) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM agent_area_data", conn)

    required = {"frame", "agent_id", "area"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"agent_area_data is missing required columns: {sorted(missing)}"
        )

    df = df.dropna(subset=["frame", "agent_id", "area"]).copy()
    df["frame"] = pd.to_numeric(df["frame"], errors="coerce")
    df = df.dropna(subset=["frame"])
    df["frame"] = df["frame"].astype(int)
    df["area"] = df["area"].astype(str)

    sample_every_frames = max(1, int(sample_every_frames))

    if sample_every_frames > 1:
        df = df[df["frame"] % sample_every_frames == 0]

    if df.empty:
        raise ValueError("No density records available after filtering")

    return (
        df.groupby(["frame", "area"], dropna=False)["agent_id"]
        .nunique()
        .reset_index(name="area_density")
    )


def select_frame(
    density_by_area_frame: pd.DataFrame,
    requested_frame: int | None,
) -> int:
    if requested_frame is not None:
        return int(requested_frame)

    peak_row = density_by_area_frame.sort_values(
        ["area_density", "frame"],
        ascending=[False, True],
    ).iloc[0]

    return int(peak_row["frame"])


def plot_density_frame(
    *,
    density_by_area_frame: pd.DataFrame,
    env,
    frame: int,
    output_path: Path,
) -> None:
    frame_density = density_by_area_frame[
        density_by_area_frame["frame"] == frame
    ].copy()

    if frame_density.empty:
        available = sorted(density_by_area_frame["frame"].unique())
        raise ValueError(
            f"No density records for frame {frame}. "
            f"Available frame range: {available[:3]} ... {available[-3:]}"
        )

    density_by_area = {
        str(row["area"]): float(row["area_density"])
        for _, row in frame_density.iterrows()
    }

    max_density = max(density_by_area.values()) if density_by_area else 1.0
    norm = Normalize(vmin=0.0, vmax=max(1.0, max_density))
    cmap = plt.get_cmap("viridis")

    fig, ax = plt.subplots(figsize=(10, 10))

    _plot_polygon_boundaries(ax, env.walkable_area, linewidth=1.0)

    for area_id, polygon_like in env.specific_areas.items():
        area_id = str(area_id)
        density = density_by_area.get(area_id, 0.0)

        for polygon in _iter_polygons(polygon_like):
            if not hasattr(polygon, "exterior"):
                continue

            x, y = polygon.exterior.xy

            ax.fill(
                x,
                y,
                color=cmap(norm(density)),
                alpha=0.85,
                linewidth=0.8,
                edgecolor="black",
            )

            centroid = polygon.centroid
            ax.text(
                centroid.x,
                centroid.y,
                f"{area_id}\n{density:.0f}",
                ha="center",
                va="center",
                fontsize=7,
            )

    ax.set_aspect("equal", adjustable="box")
    ax.set_title(
        f"Area density by frame | frame={frame} | "
        "density=count(distinct agents in area)"
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    colorbar = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        ax=ax,
        fraction=0.046,
        pad=0.04,
    )
    colorbar.set_label("Area density [agents per area/frame]")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def default_output_path(db_path: Path, frame: int) -> Path:
    # Expected db layout: <case>/artifacts/db/simulation.db
    artifacts_dir = db_path.parent.parent
    return artifacts_dir / "img" / f"density_frame_{frame}.png"


def main() -> int:
    args = parse_args()

    db_path = Path(args.db).resolve()
    case_cfg = load_case_config(args.config, args.case)
    env = select_environment(case_cfg["environment"])

    density_by_area_frame = load_density_by_area_frame(
        db_path,
        sample_every_frames=args.sample_every_frames,
    )

    frame = select_frame(
        density_by_area_frame,
        args.frame,
    )

    output_path = (
        Path(args.output).resolve()
        if args.output
        else default_output_path(db_path, frame)
    )

    plot_density_frame(
        density_by_area_frame=density_by_area_frame,
        env=env,
        frame=frame,
        output_path=output_path,
    )

    print(f"Density image written: {output_path}")
    print(f"Frame selected: {frame}")
    print(
        "Peak area_density in frame: "
        f"{density_by_area_frame[density_by_area_frame['frame'] == frame]['area_density'].max()}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
