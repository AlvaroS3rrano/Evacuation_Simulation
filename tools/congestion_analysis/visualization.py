from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize


HEURISTIC_ORDER = ["none", "h1", "h2", "h3"]

FRAME_COLUMN_CANDIDATES = ["frame", "iteration", "frame_id", "step", "timestep"]
AGENT_COLUMN_CANDIDATES = ["agent_id", "id", "agent", "pedestrian_id", "ped_id"]
X_COLUMN_CANDIDATES = ["x", "pos_x", "position_x", "x_position"]
Y_COLUMN_CANDIDATES = ["y", "pos_y", "position_y", "y_position"]
GEOMETRY_COLUMN_CANDIDATES = ["point", "position", "geometry", "geom", "coordinate"]


@dataclass(frozen=True)
class RunVisualRecord:
    case_id: str
    heuristic: str
    run_dir: Path
    simulation_db_path: Path


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML file must be a mapping: {path}")

    return data


def resolve_config_path(project_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None

    if path.exists():
        return path.resolve()

    candidate = project_root / "configs" / path
    if candidate.exists():
        return candidate.resolve()

    raise FileNotFoundError(f"Config not found: {path}")


def load_case_config(
    *,
    project_root: Path,
    case_id: str,
    simulation_config: Path | None,
) -> tuple[dict[str, Any], Path]:
    if simulation_config is not None:
        config_path = resolve_config_path(project_root, simulation_config)
        assert config_path is not None
        data = _load_yaml(config_path)

        if case_id not in data:
            raise KeyError(f"Case {case_id!r} not found in {config_path}")

        case_cfg = data[case_id]
        if not isinstance(case_cfg, dict):
            raise TypeError(f"Case {case_id!r} must be a mapping in {config_path}")

        return case_cfg, config_path

    config_paths = list((project_root / "configs").glob("*.yaml"))
    config_paths += list((project_root / "configs").glob("*.yml"))

    for config_path in sorted(config_paths):
        data = _load_yaml(config_path)
        if case_id in data and isinstance(data[case_id], dict):
            return data[case_id], config_path

    raise KeyError(f"Could not find case {case_id!r} under {project_root / 'configs'}")


def _as_polygon(geometry_like: Any) -> Any:
    return getattr(geometry_like, "polygon", geometry_like)


def _iter_polygons(geometry_like: Any) -> list[Any]:
    polygon = _as_polygon(geometry_like)
    if hasattr(polygon, "geoms"):
        return list(polygon.geoms)
    return [polygon]


def _plot_polygon_boundaries(
    ax,
    geometry_like: Any,
    *,
    linewidth: float = 1.0,
    alpha: float = 1.0,
) -> None:
    for polygon in _iter_polygons(geometry_like):
        if not hasattr(polygon, "exterior"):
            continue

        x, y = polygon.exterior.xy
        ax.plot(x, y, linewidth=linewidth, alpha=alpha, color="black")

        for interior in getattr(polygon, "interiors", []):
            ix, iy = interior.xy
            ax.plot(ix, iy, linewidth=linewidth, alpha=alpha, color="black")


def sqlite_has_table(db_path: Path, table_name: str) -> bool:
    if not db_path.exists():
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
    except sqlite3.Error:
        return False

    return row is not None


def choose_trajectory_db(run_dir: Path) -> Path | None:
    db_paths = sorted(run_dir.rglob("*.db"))

    if not db_paths:
        return None

    preferred = [
        path
        for path in db_paths
        if path.name.lower() != "simulation.db" and sqlite_has_table(path, "trajectory_data")
    ]
    if preferred:
        return preferred[0]

    fallback = [
        path
        for path in db_paths
        if sqlite_has_table(path, "trajectory_data")
    ]
    return fallback[0] if fallback else None


def choose_trajectory_image(run_dir: Path) -> Path | None:
    images_dir = run_dir / "artifacts" / "images"
    if not images_dir.exists():
        return None

    patterns = [
        "*trajectories.png",
        "*trajectory*.png",
    ]

    for pattern in patterns:
        matches = sorted(images_dir.glob(pattern))
        if matches:
            return matches[0]

    return None


def _detect_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    lower_map = {column.lower(): column for column in columns}

    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]

    return None


def _parse_point_like(value: Any) -> tuple[float | None, float | None]:
    if value is None:
        return None, None

    text = str(value)

    match = re.search(
        r"POINT\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return float(match.group(1)), float(match.group(2))

    numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])

    return None, None


def load_trajectory_dataframe(
    db_path: Path,
    *,
    frame_stride: int = 10,
    max_agents: int | None = 300,
) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"Trajectory database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query('SELECT * FROM "trajectory_data"', conn)

    if df.empty:
        raise ValueError(f"trajectory_data is empty in {db_path}")

    columns = list(df.columns)
    frame_col = _detect_column(columns, FRAME_COLUMN_CANDIDATES)
    agent_col = _detect_column(columns, AGENT_COLUMN_CANDIDATES)
    x_col = _detect_column(columns, X_COLUMN_CANDIDATES)
    y_col = _detect_column(columns, Y_COLUMN_CANDIDATES)
    geometry_col = _detect_column(columns, GEOMETRY_COLUMN_CANDIDATES)

    if frame_col is None:
        raise RuntimeError(f"No frame column detected in trajectory_data columns={columns}")

    if agent_col is None:
        df["_agent_id"] = df.groupby(frame_col).cumcount()
        agent_col = "_agent_id"

    result = pd.DataFrame()
    result["frame"] = pd.to_numeric(df[frame_col], errors="coerce")
    result["agent_id"] = df[agent_col].astype(str)

    if x_col is not None and y_col is not None:
        result["x"] = pd.to_numeric(df[x_col], errors="coerce")
        result["y"] = pd.to_numeric(df[y_col], errors="coerce")
    elif geometry_col is not None:
        parsed = df[geometry_col].map(_parse_point_like)
        result["x"] = [xy[0] for xy in parsed]
        result["y"] = [xy[1] for xy in parsed]
    else:
        raise RuntimeError(
            "No x/y columns or point-like geometry column detected in trajectory_data"
        )

    result = result.dropna(subset=["frame", "x", "y"]).copy()
    result["frame"] = result["frame"].astype(int)

    frame_stride = max(1, int(frame_stride))
    if frame_stride > 1:
        result = result[result["frame"] % frame_stride == 0].copy()

    if max_agents is not None:
        selected_agents = result["agent_id"].drop_duplicates().head(int(max_agents))
        result = result[result["agent_id"].isin(selected_agents)].copy()

    return result.sort_values(["agent_id", "frame"]).reset_index(drop=True)


def load_area_density_from_db(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f"Simulation database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT frame, agent_id, area FROM agent_area_data", conn)

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

    return (
        df.groupby(["frame", "area"], dropna=False)["agent_id"]
        .nunique()
        .reset_index(name="area_density")
    )


def build_density_map_for_frame(
    density_df: pd.DataFrame,
    frame: int,
) -> dict[str, float]:
    frame_df = density_df[density_df["frame"] == int(frame)]
    if frame_df.empty:
        return {}

    return {
        str(row["area"]): float(row["area_density"])
        for _, row in frame_df.iterrows()
    }


def build_visual_records(summary: pd.DataFrame) -> list[RunVisualRecord]:
    records: list[RunVisualRecord] = []

    required = {"case_id", "heuristic", "run_dir", "simulation_db_path"}
    if not required.issubset(summary.columns):
        return records

    compact = summary[["case_id", "heuristic", "run_dir", "simulation_db_path"]].drop_duplicates()

    for _, row in compact.iterrows():
        run_dir = Path(str(row["run_dir"]))
        simulation_db_path = Path(str(row["simulation_db_path"]))

        records.append(
            RunVisualRecord(
                case_id=str(row["case_id"]),
                heuristic=str(row["heuristic"]),
                run_dir=run_dir,
                simulation_db_path=simulation_db_path,
            )
        )

    return records


def _plot_trajectory_image_panel(
    *,
    ax,
    heuristic: str,
    image_path: Path | None,
) -> None:
    if image_path is None or not image_path.exists():
        ax.text(
            0.5,
            0.5,
            "No trajectory image",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=11,
        )
        ax.set_title(heuristic)
        ax.axis("off")
        return

    image = plt.imread(image_path)
    ax.imshow(image)
    ax.set_title(heuristic)
    ax.axis("off")


def _plot_trajectory_panel(
    *,
    ax,
    env: Any,
    heuristic: str,
    trajectory_df: pd.DataFrame | None,
) -> None:
    _plot_polygon_boundaries(ax, env.walkable_area, linewidth=1.0, alpha=0.9)

    if trajectory_df is None or trajectory_df.empty:
        ax.text(
            0.5,
            0.5,
            "No trajectory data",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=11,
        )
    else:
        for _, agent_df in trajectory_df.groupby("agent_id", sort=False):
            if len(agent_df) < 2:
                continue
            ax.plot(
                agent_df["x"],
                agent_df["y"],
                linewidth=0.45,
                alpha=0.32,
            )

        first_points = trajectory_df.sort_values("frame").groupby("agent_id").head(1)
        last_points = trajectory_df.sort_values("frame").groupby("agent_id").tail(1)

        ax.scatter(first_points["x"], first_points["y"], s=4, alpha=0.45, label="start")
        ax.scatter(last_points["x"], last_points["y"], s=4, alpha=0.45, marker="x", label="end")

        ax.text(
            0.02,
            0.02,
            f"agents={trajectory_df['agent_id'].nunique()} frames={trajectory_df['frame'].nunique()}",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
        )

    ax.set_title(heuristic)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _plot_density_panel(
    *,
    ax,
    env: Any,
    heuristic: str,
    density_map: dict[str, float] | None,
    norm: Normalize,
    cmap: Any,
    frame: int,
) -> None:
    _plot_polygon_boundaries(ax, env.walkable_area, linewidth=1.0, alpha=0.85)

    if density_map is None:
        ax.text(
            0.5,
            0.5,
            "No run data",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=11,
        )
        ax.set_title(heuristic)
        ax.set_aspect("equal", adjustable="box")
        return

    if not density_map:
        ax.text(
            0.5,
            0.5,
            f"No density data\nframe={frame}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=10,
        )
        ax.set_title(heuristic)
        ax.set_aspect("equal", adjustable="box")
        return

    max_panel_density = max(density_map.values()) if density_map else 0.0

    for area_id, polygon_like in env.specific_areas.items():
        area_key = str(area_id)
        density = float(density_map.get(area_key, 0.0))

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
                f"{area_key}\n{density:.0f}",
                ha="center",
                va="center",
                fontsize=6,
            )

    ax.set_title(f"{heuristic} | max={max_panel_density:.0f}")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def _ordered_heuristics(
    available: set[str],
    requested: Sequence[str],
) -> list[str]:
    ordered = [heuristic for heuristic in requested if heuristic in available]
    for heuristic in HEURISTIC_ORDER:
        if heuristic in available and heuristic not in ordered:
            ordered.append(heuristic)
    return ordered[:4]


def _create_2x2_figure(
    *,
    title: str,
    with_sidebar: bool,
) -> tuple[Any, list[Any]]:
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    axes_flat = list(axes.flat)
    fig.suptitle(title, fontsize=14)

    if with_sidebar:
        fig.subplots_adjust(
            left=0.055,
            right=0.84,
            top=0.91,
            bottom=0.06,
            wspace=0.18,
            hspace=0.24,
        )
    else:
        fig.subplots_adjust(
            left=0.055,
            right=0.96,
            top=0.91,
            bottom=0.06,
            wspace=0.10,
            hspace=0.18,
        )

    return fig, axes_flat


def _common_terminal_frame(
    density_tables: dict[str, pd.DataFrame | None],
) -> int | None:
    terminal_frames = [
        int(df["frame"].max())
        for df in density_tables.values()
        if df is not None and not df.empty
    ]

    if not terminal_frames:
        return None

    return min(terminal_frames)


def build_density_frames(
    *,
    density_tables: dict[str, pd.DataFrame | None],
    explicit_frames: Sequence[int] | None,
    frame_step: int,
    include_terminal_frame: bool = True,
) -> list[int]:
    terminal_frame = _common_terminal_frame(density_tables)
    if terminal_frame is None:
        return []

    if explicit_frames:
        frames = sorted({
            int(frame)
            for frame in explicit_frames
            if int(frame) >= 0 and int(frame) <= terminal_frame
        })
        if not frames:
            frames = [terminal_frame]
        return frames

    frame_step = max(1, int(frame_step))
    frames = list(range(0, terminal_frame + 1, frame_step))

    if include_terminal_frame and terminal_frame not in frames:
        frames.append(terminal_frame)

    return frames


def generate_visual_comparison_pdfs(
    *,
    summary: pd.DataFrame,
    project_root: Path,
    comparison_dir: Path,
    simulation_config: Path | None,
    heuristics: Sequence[str],
    density_frames: Sequence[int] | None,
    density_frame_step: int = 500,
    include_terminal_density_frame: bool = True,
    visual_subdir: str = "visual_snapshots",
    trajectory_frame_stride: int = 10,
    trajectory_max_agents: int | None = 300,
) -> list[Path]:
    from evac_sim.envs.environment_factory import select_environment

    visual_dir = comparison_dir / visual_subdir
    visual_dir.mkdir(parents=True, exist_ok=True)

    records = build_visual_records(summary)
    by_case: dict[str, dict[str, RunVisualRecord]] = {}

    for record in records:
        by_case.setdefault(record.case_id, {})[record.heuristic] = record

    pdf_paths: list[Path] = []

    for case_id in sorted(by_case):
        case_records = by_case[case_id]
        selected_heuristics = _ordered_heuristics(
            available=set(case_records),
            requested=heuristics,
        )

        try:
            case_cfg, used_config = load_case_config(
                project_root=project_root,
                case_id=case_id,
                simulation_config=simulation_config,
            )
            env = select_environment(case_cfg["environment"])
        except Exception as exc:
            print(f"[visual] SKIP case={case_id} reason={exc}")
            continue

        density_tables: dict[str, pd.DataFrame | None] = {}
        trajectory_tables: dict[str, pd.DataFrame | None] = {}
        trajectory_images: dict[str, Path | None] = {}

        for heuristic in selected_heuristics:
            record = case_records.get(heuristic)

            if record is None:
                density_tables[heuristic] = None
                trajectory_tables[heuristic] = None
                trajectory_images[heuristic] = None
                continue

            trajectory_images[heuristic] = choose_trajectory_image(record.run_dir)

            try:
                density_tables[heuristic] = load_area_density_from_db(record.simulation_db_path)
            except Exception as exc:
                print(f"[visual] WARN density case={case_id} heuristic={heuristic} error={exc}")
                density_tables[heuristic] = None

            if trajectory_images[heuristic] is None:
                try:
                    trajectory_db = choose_trajectory_db(record.run_dir)
                    trajectory_tables[heuristic] = (
                        load_trajectory_dataframe(
                            trajectory_db,
                            frame_stride=trajectory_frame_stride,
                            max_agents=trajectory_max_agents,
                        )
                        if trajectory_db is not None
                        else None
                    )
                except Exception as exc:
                    print(f"[visual] WARN trajectory case={case_id} heuristic={heuristic} error={exc}")
                    trajectory_tables[heuristic] = None
            else:
                trajectory_tables[heuristic] = None

        selected_density_frames = build_density_frames(
            density_tables=density_tables,
            explicit_frames=density_frames,
            frame_step=density_frame_step,
            include_terminal_frame=include_terminal_density_frame,
        )

        pdf_path = visual_dir / f"{case_id}_visual_comparison.pdf"

        with PdfPages(pdf_path) as pdf:
            metadata = pdf.infodict()
            metadata["Title"] = f"Visual comparison - {case_id}"
            metadata["Author"] = "compare_congestion_heuristics.py"
            metadata["Subject"] = "Trajectories and density snapshots by congestion heuristic."
            metadata["Keywords"] = "trajectory density congestion heuristics"

            # Page 1: trajectories.
            fig, axes = _create_2x2_figure(
                title=f"{case_id} | trajectories | config={used_config.name}",
                with_sidebar=False,
            )

            for idx, heuristic in enumerate(selected_heuristics[:4]):
                if trajectory_images.get(heuristic) is not None:
                    _plot_trajectory_image_panel(
                        ax=axes[idx],
                        heuristic=heuristic,
                        image_path=trajectory_images.get(heuristic),
                    )
                else:
                    _plot_trajectory_panel(
                        ax=axes[idx],
                        env=env,
                        heuristic=heuristic,
                        trajectory_df=trajectory_tables.get(heuristic),
                    )

            for idx in range(len(selected_heuristics[:4]), 4):
                axes[idx].axis("off")

            pdf.savefig(fig)
            plt.close(fig)

            # Following pages: density snapshots.
            for frame in selected_density_frames:
                panel_maps: dict[str, dict[str, float] | None] = {}
                max_density = 0.0

                for heuristic in selected_heuristics:
                    density_df = density_tables.get(heuristic)
                    if density_df is None:
                        panel_maps[heuristic] = None
                        continue

                    density_map = build_density_map_for_frame(
                        density_df,
                        int(frame),
                    )
                    panel_maps[heuristic] = density_map

                    if density_map:
                        max_density = max(max_density, max(density_map.values()))

                norm = Normalize(vmin=0.0, vmax=max(1.0, max_density))
                cmap = plt.get_cmap("viridis")

                fig, axes = _create_2x2_figure(
                    title=(
                        f"{case_id} | density frame={frame} | "
                        "density=count(distinct agents in area)"
                    ),
                    with_sidebar=True,
                )

                for idx, heuristic in enumerate(selected_heuristics[:4]):
                    _plot_density_panel(
                        ax=axes[idx],
                        env=env,
                        heuristic=heuristic,
                        density_map=panel_maps.get(heuristic),
                        norm=norm,
                        cmap=cmap,
                        frame=int(frame),
                    )

                for idx in range(len(selected_heuristics[:4]), 4):
                    axes[idx].axis("off")

                cax = fig.add_axes([0.87, 0.18, 0.018, 0.64])
                cbar = fig.colorbar(
                    ScalarMappable(norm=norm, cmap=cmap),
                    cax=cax,
                )
                cbar.set_label("Area density [agents per area/frame]")

                pdf.savefig(fig)
                plt.close(fig)

        pdf_paths.append(pdf_path)
        print(f"Visual comparison PDF: {pdf_path}")

    return pdf_paths
