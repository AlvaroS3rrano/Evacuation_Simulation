# Copyright © 2012-2024 Forschungszentrum Jülich GmbH
# SPDX-License-Identifier: LGPL-3.0-or-later

"""This code is used in examples on jupedsim.org.

We make no promises about the functions from this file with respect to API stability. We
reserve the right to change the code here without warning. Do not use the
code here. Use it at your own risk.
"""

import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pedpy
import plotly.graph_objects as go

DUMMY_SPEED = -1000


def read_sqlite_file(
    trajectory_file: str,
) -> tuple[pedpy.TrajectoryData, pedpy.WalkableArea]:
    """Read trajectory and walkable area data from a SQLite file.

    Returns:
        A tuple containing:
          - pedpy.TrajectoryData with columns: frame, id, x, y, ox, oy
          - pedpy.WalkableArea representing the walkable polygon.
    """
    with sqlite3.connect(trajectory_file) as con:
        data = pd.read_sql_query(
            "select frame, id, pos_x as x, pos_y as y, ori_x as ox, ori_y as oy from trajectory_data",
            con,
        )
        fps = float(
            con.cursor()
            .execute("select value from metadata where key = 'fps'")
            .fetchone()[0]
        )
        walkable_area = (
            con.cursor().execute("select wkt from geometry").fetchone()[0]
        )
        return (
            pedpy.TrajectoryData(data=data, frame_rate=fps),
            pedpy.WalkableArea(walkable_area),
        )


def _speed_to_color(speed, min_speed, max_speed):
    """Map a speed value to a color using a colormap."""
    normalized_speed = (speed - min_speed) / (max_speed - min_speed)
    r, g, b = plt.cm.jet_r(normalized_speed)[:3]
    return f"rgba({r*255:.0f}, {g*255:.0f}, {b*255:.0f}, 0.5)"


def _get_line_color(disk_color):
    """Choose black or white text based on disk_color brightness."""
    r, g, b, _ = [int(float(val)) for val in disk_color[5:-2].split(",")]
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "black" if brightness > 127 else "white"


def _create_orientation_line(row, line_length=0.2, color="black"):
    """Create a Plotly shape for the agent's orientation line."""
    end_x = row["x"] + line_length * row["ox"]
    end_y = row["y"] + line_length * row["oy"]

    orientation_line = go.layout.Shape(
        type="line",
        x0=row["x"],
        y0=row["y"],
        x1=end_x,
        y1=end_y,
        line=dict(color=color, width=3),
    )
    return orientation_line


#######################################################

def _get_waypoint_traces(waypoint_coords):
    """Generate Scatter traces for waypoints (markers + labels)."""
    waypoint_traces = []
    for i, (x, y) in enumerate(waypoint_coords):
        waypoint_traces.append(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                marker=dict(size=10, color="red", symbol="cross"),
                text=[f"W{i+1}"],  # waypoint label
                textposition="top center",
                showlegend=False,
                hoverinfo="skip",
            )
        )
    return waypoint_traces


#######################################################

def _get_geometry_traces(area):
    """
    Generate geometry traces for plotting the exterior and interior boundaries
    (e.g., obstacles) of an area. Interior can be filled differently if needed.

    Parameters:
        area: A polygon object representing the walkable area, with .exterior and .interiors.

    Returns:
        geometry_traces: A list of Plotly Scatter traces for the polygon boundaries.
    """
    geometry_traces = []

    # Exterior boundary of the area
    x, y = area.exterior.xy
    geometry_traces.append(
        go.Scatter(
            x=np.array(x),
            y=np.array(y),
            mode="lines",
            line={"color": "black"},  # draw exterior in black
            showlegend=False,
            name="Exterior",
            hoverinfo="name",
        )
    )

    # Interior boundaries (obstacles)
    for inner in area.interiors:
        xi, yi = zip(*inner.coords[:])
        geometry_traces.append(
            go.Scatter(
                x=np.array(xi),
                y=np.array(yi),
                mode="lines",
                line={"color": "black"},  # draw obstacles in black
                showlegend=False,
                name="Obstacle",
                hoverinfo="name",
            )
        )

    return geometry_traces


def _change_geometry_traces(geometry_traces, specific_area, color):
    """
    Update geometry traces to fill a specific area with a given color.

    Parameters:
        geometry_traces: Existing list of geometry traces.
        specific_area: A polygon to fill with the given color.
        color: Fill color for the specific area.

    Returns:
        Updated list of geometry traces including the filled area.
    """
    x, y = specific_area.exterior.xy
    geometry_traces.append(
        go.Scatter(
            x=np.array(x),
            y=np.array(y),
            mode="lines",
            line={"width": 0},  # no outline, only fill
            fill="toself",
            fillcolor=color,
            showlegend=False,
            name="Risk Area",
            hoverinfo="name",
        )
    )
    return geometry_traces


def _get_colormap(frame_data, max_speed):
    """Generate a scatter plot trace only to include a colorbar for speeds."""
    scatter_trace = go.Scatter(
        x=frame_data["x"],
        y=frame_data["y"],
        mode="markers",
        marker=dict(
            size=frame_data["radius"] * 2,
            color=frame_data["speed"],
            colorscale="Jet_r",
            colorbar=dict(title="Speed [m/s]"),
            cmin=0,
            cmax=max_speed,
        ),
        text=frame_data["speed"],
        showlegend=False,
        hoverinfo="none",
    )

    return [scatter_trace]


def _get_shapes_for_frame(frame_data, min_speed, max_speed):
    """Create Plotly shapes, hover traces, and orientation arrows for each agent in one frame."""
    def create_shape(row):
        hover_trace = go.Scatter(
            x=[row["x"]],
            y=[row["y"]],
            text=[f"ID: {row['id']}, Pos({row['x']:.2f},{row['y']:.2f})"],
            mode="markers",
            marker=dict(size=1, opacity=1),
            hoverinfo="text",
            showlegend=False,
        )
        if row["speed"] == DUMMY_SPEED:
            # Dummy agent: draw transparent circle, no hover
            dummy_trace = go.Scatter(
                x=[row["x"]],
                y=[row["y"]],
                mode="markers",
                marker=dict(size=1, opacity=0),
                hoverinfo="none",
                showlegend=False,
            )
            return (
                go.layout.Shape(
                    type="circle",
                    xref="x",
                    yref="y",
                    x0=row["x"] - row["radius"],
                    y0=row["y"] - row["radius"],
                    x1=row["x"] + row["radius"],
                    y1=row["y"] + row["radius"],
                    line=dict(width=0),
                    fillcolor="rgba(255,255,255,0)",  # Transparent fill
                ),
                dummy_trace,
                _create_orientation_line(row, color="rgba(255,255,255,0)"),
            )
        color = _speed_to_color(row["speed"], min_speed, max_speed)
        return (
            go.layout.Shape(
                type="circle",
                xref="x",
                yref="y",
                x0=row["x"] - row["radius"],
                y0=row["y"] - row["radius"],
                x1=row["x"] + row["radius"],
                y1=row["y"] + row["radius"],
                line_color=color,
                fillcolor=color,
            ),
            hover_trace,
            _create_orientation_line(row, color=_get_line_color(color)),
        )

    results = frame_data.apply(create_shape, axis=1).tolist()
    shapes = [res[0] for res in results]
    hover_traces = [res[1] for res in results]
    arrows = [res[2] for res in results]
    return shapes, hover_traces, arrows


def _create_fig(
    initial_agent_count,
    initial_shapes,
    initial_arrows,
    initial_hover_trace,
    initial_scatter_trace,
    geometry_traces,
    frames,
    steps,
    area_bounds,
    width=800,
    height=800,
    title_note: str = "",
):
    """Create a Plotly Figure with animation controls for the simulation.

    Returns:
        A go.Figure object with animation frames and layout configured.
    """
    minx, miny, maxx, maxy = area_bounds
    title = f"<b>{title_note + '  |  ' if title_note else ''}Number of Agents: {initial_agent_count}</b>"

    fig = go.Figure(
        data=geometry_traces
        + initial_scatter_trace
        + initial_hover_trace,
        frames=frames,
        layout=go.Layout(
            shapes=initial_shapes + initial_arrows, title=title, title_x=0.5
        ),
    )
    fig.update_layout(
        updatemenus=[_get_animation_controls()],
        sliders=[_get_slider_controls(steps)],
        autosize=False,
        width=width,
        height=height,
        xaxis=dict(range=[minx - 0.5, maxx + 0.5]),
        yaxis=dict(
            scaleanchor="x", scaleratio=1, range=[miny - 0.5, maxy + 0.5]
        ),
    )

    return fig


def _get_animation_controls():
    """Return the Play button controls for the animation."""
    return {
        "buttons": [
            {
                "args": [
                    None,
                    {
                        "frame": {"duration": 100, "redraw": True},
                        "fromcurrent": True,
                    },
                ],
                "label": "Play",
                "method": "animate",
            },
        ],
        "direction": "left",
        "pad": {"r": 10, "t": 87},
        "showactive": False,
        "type": "buttons",
        "x": 0.1,
        "xanchor": "right",
        "y": 0,
        "yanchor": "top",
    }


def _get_slider_controls(steps):
    """Return the slider configuration for the animation frames."""
    return {
        "active": 0,
        "yanchor": "top",
        "xanchor": "left",
        "currentvalue": {
            "font": {"size": 20},
            "prefix": "Frame:",
            "visible": True,
            "xanchor": "right",
        },
        "transition": {"duration": 100, "easing": "cubic-in-out"},
        "pad": {"b": 10, "t": 50},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": steps,
    }


def _get_processed_frame_data(data_df, frame_num, max_agents):
    """Ensure each frame has exactly max_agents rows by adding dummy agents if needed."""
    frame_data = data_df[data_df["frame"] == frame_num]
    agent_count = len(frame_data)
    dummy_agent_data = {"x": 0, "y": 0, "radius": 0, "speed": DUMMY_SPEED}
    while len(frame_data) < max_agents:
        dummy_df = pd.DataFrame([dummy_agent_data])
        frame_data = pd.concat([frame_data, dummy_df], ignore_index=True)
    return frame_data, agent_count


def generate_risk_colors(risk_threshold=0.5):
    """
    Generate a list of RGBA color strings for risk levels 0 to 10.
    - Below risk_threshold: transparent pink to opaque pink.
    - Above risk_threshold: gradient from light purple to dark purple.
    """
    colors = []
    # Base color for low risk (pink)
    first_color = (255, 192, 203)
    # Light and dark purple for high risk gradient
    light_purple = (221, 160, 221)
    dark_purple = (128, 0, 128)

    for i in range(11):  # Risk levels 0 to 10
        normalized_risk = i / 10.0
        if normalized_risk < risk_threshold:
            # Low risk: alpha from 0 to 1
            fraction = normalized_risk / risk_threshold if risk_threshold != 0 else 0
            alpha = fraction
            color = f"rgba({first_color[0]}, {first_color[1]}, {first_color[2]}, {alpha:.2f})"
        else:
            # High risk: interpolate between light purple and dark purple
            fraction = (normalized_risk - risk_threshold) / (1 - risk_threshold) if risk_threshold != 1 else 0
            r = int(light_purple[0] + fraction * (dark_purple[0] - light_purple[0]))
            g = int(light_purple[1] + fraction * (dark_purple[1] - light_purple[1]))
            b = int(light_purple[2] + fraction * (dark_purple[2] - light_purple[2]))
            color = f"rgba({r}, {g}, {b}, 1)"
        colors.append(color)
    return colors


def add_static_risk_colorbar():
    """
    Create a Scatter trace representing a static risk level colorbar from black to red.

    Returns:
        A go.Scatter trace with the risk colorbar.
    """
    # Generate the color scale from black to red
    risk_colors = generate_risk_colors()  # e.g., ['rgba(255,192,203,0.0)', ..., 'rgba(128,0,128,1)']

    # Convert risk_colors into Plotly-compatible colorscale tuples
    colorscale = [
        (i / (len(risk_colors) - 1), color)  # Normalize positions 0 to 1
        for i, color in enumerate(risk_colors)
    ]

    # Dummy data to attach the colorbar
    dummy_x = [0]
    dummy_y = [0]

    risk_trace = go.Scatter(
        x=dummy_x,
        y=dummy_y,
        mode="markers",
        marker=dict(
            size=10,  # small dummy marker
            color=[0],  # only one dummy value
            colorscale=colorscale,  # custom black-to-red scale
            colorbar=dict(
                title="Risk Level",  # label for the colorbar
                x=1.25,  # position to the right of the plot
            ),
            cmin=0,  # minimum = black
            cmax=1,  # maximum = red
        ),
        showlegend=False,
        hoverinfo="none",  # no hover for dummy
    )
    return risk_trace


def animate(
    data: pedpy.TrajectoryData,  # TrajectoryData with positions and frame info
    area: pedpy.WalkableArea,    # WalkableArea polygon
    *,
    every_nth_frame: int = 50,   # Subsample frequency for frames
    width: int = 800,            # Figure width in pixels
    height: int = 800,           # Figure height in pixels
    radius: float = 0.2,         # Visual radius for agents
    title_note: str = "",        # Optional title annotation
    waypoint_coords=None,        # Optional waypoint coordinates
    risk_per_frame: dict = None, # Risk levels per frame
    specific_areas: dict = None, # Polygons to highlight for risk
):
    """
    Create an animated Plotly Figure showing trajectories, walkable area, agent speeds, and risk zones.

    Returns:
        A Plotly go.Figure object configured with frames and animation controls.
    """
    # Compute individual speeds for each agent
    data_df = pedpy.compute_individual_speed(
        traj_data=data,  # trajectory data
        frame_step=5,  # frame interval to compute speeds
        speed_calculation=pedpy.SpeedCalculation.BORDER_SINGLE_SIDED,
    )

    # Merge computed speeds back into original data
    data_df = data_df.merge(data.data, on=["id", "frame"], how="left")

    # Add radius column for marker size
    data_df["radius"] = radius

    # Determine min and max speeds for color mapping
    min_speed = data_df["speed"].min()
    max_speed = data_df["speed"].max()

    # Find maximum number of agents in any single frame
    max_agents = data_df.groupby("frame").size().max()

    # Prepare lists for frames and slider steps
    frames = []
    steps = []

    # Get list of unique frame indices and select every nth frame
    unique_frames = data_df["frame"].unique()
    selected_frames = unique_frames[::every_nth_frame]

    # Create geometry traces (exterior and interior boundaries)
    geometry_traces = _get_geometry_traces(area.polygon)

    # If waypoints are provided, add them
    if waypoint_coords:
        waypoint_traces = _get_waypoint_traces(waypoint_coords)
        geometry_traces.extend(waypoint_traces)

    # Data for the first frame (initial state)
    initial_frame_data = data_df[data_df["frame"] == data_df["frame"].min()]
    initial_agent_count = len(initial_frame_data)

    # Generate initial agent shapes, hover traces, and orientation arrows
    (
        initial_shapes,
        initial_hover_trace,
        initial_arrows,
    ) = _get_shapes_for_frame(initial_frame_data, min_speed, max_speed)

    # Generate a colorbar trace for speeds
    color_map_trace = _get_colormap(initial_frame_data, max_speed)
    # Generate a static risk colorbar
    risk_trace = add_static_risk_colorbar()

    # Combine traces for the initial layout
    traces = color_map_trace + [risk_trace]

    # Precompute risk color gradient
    risk_colors = generate_risk_colors()

    # Process each selected frame
    for frame_num in selected_frames:
        # Get processed data for this frame (ensuring max_agents rows)
        frame_data, agent_count = _get_processed_frame_data(
            data_df, frame_num, max_agents
        )
        # Recompute geometry traces each frame in case risk zones change
        geometry_traces = _get_geometry_traces(area.polygon)

        # If specific risk areas and risk_per_frame are provided, color them
        if specific_areas and risk_per_frame:
            current_risks = risk_per_frame.get(frame_num, {})  # risk levels for this frame
            for area_name, risk_level in current_risks.items():
                color = risk_colors[int(risk_level * 10)]  # map risk level to 0-10 index
                specific_area = specific_areas[area_name]
                geometry_traces = _change_geometry_traces(geometry_traces, specific_area, color)

        # Generate shapes, hover traces, and orientation arrows for this frame
        shapes, hover_traces, arrows = _get_shapes_for_frame(
            frame_data, min_speed, max_speed
        )

        # Construct dynamic title for this frame
        title = f"<b>{title_note + '  |  ' if title_note else ''}Number of Agents: {agent_count}</b>"

        # Frame name as string
        frame_name = str(int(frame_num))

        # Create a go.Frame object with data and layout for this frame
        frame = go.Frame(
            data=geometry_traces + hover_traces,
            name=frame_name,
            layout=go.Layout(
                shapes=shapes + arrows,
                title=title,
                title_x=0.5,
            ),
        )
        frames.append(frame)

        # Create slider step entry
        step = {
            "args": [
                [frame_name],
                {
                    "frame": {"duration": 100, "redraw": True},
                    "mode": "immediate",
                    "transition": {"duration": 500},
                },
            ],
            "label": frame_name,
            "method": "animate",
        }
        steps.append(step)

    # Build and return the final animated figure
    return _create_fig(
        initial_agent_count,
        initial_shapes,
        initial_arrows,
        initial_hover_trace,
        traces,
        geometry_traces,
        frames,
        steps,
        area.bounds,
        width=width,
        height=height,
        title_note=title_note,
    )
