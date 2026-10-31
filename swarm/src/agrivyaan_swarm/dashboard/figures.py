"""Pure Plotly figure builders for visual simulation replay and comparison."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import plotly.graph_objects as go
from agrivyaan_swarm.models.recording import RunRecording

# Color-blind safe palette for drone ownership
# Drone 0 = Master Drone (Royal Blue), Drone 1 = Magenta/Coral, Drone 2 = Teal/Cyan, etc.
DRONE_PALETTE = ["#1976d2", "#e91e63", "#0097a7", "#ff9800", "#7b1fa2"]

# Task status fallback colors
TASK_STATUS_COLORS = {
    "PENDING": "#ff9800",
    "ASSIGNED": "#1976d2",
    "IN_PROGRESS": "#9c27b0",
    "COMPLETED": "#4caf50",
    "UNREACHABLE": "#f44336",
}

ANOMALY_LABELS = [
    "Early Blight Lesion",
    "Leaf Chlorosis (Yellowing)",
    "Stunted Canopy Growth",
]


def build_mission_replay_figure(
    recording: RunRecording,
    frame_idx: int = 0,
    farm_image_b64: Optional[str] = None,
    master_drone_b64: Optional[str] = None,
    swarm_drone_b64: Optional[str] = None,
    field_width_m: Optional[float] = None,
    field_height_m: Optional[float] = None,
    origin_lat_lon: Optional[tuple[float, float]] = None,
    use_satellite: bool = False,
) -> go.Figure:
    """Build pure Plotly 2D farm figure representing the simulation state at frame_idx.

    Pure function: RunRecording + frame index + assets -> go.Figure.
    """
    if not recording.frames:
        fig = go.Figure()
        fig.update_layout(title="No simulation frames available.")
        return fig

    # Clamp frame_idx to valid range
    idx = max(0, min(frame_idx, len(recording.frames) - 1))
    frame = recording.frames[idx]

    field_data = recording.scenario.get("field", {})
    width = float(field_width_m or field_data.get("width_m", 100.0))
    height = float(field_height_m or field_data.get("height_m", 100.0))
    base = field_data.get("base_position", [0.0, 0.0])

    fig = go.Figure()

    # 1. Background Farm Map Image (if provided)
    if farm_image_b64:
        fig.add_layout_image(
            dict(
                source=farm_image_b64,
                xref="x",
                yref="y",
                x=0,
                y=height,
                sizex=width,
                sizey=height,
                sizing="stretch",
                opacity=0.88,
                layer="below",
            )
        )
    else:
        # Subtle agricultural grid overlay if no farm background is supplied
        row_step = 10.0
        for r in range(int(height // row_step)):
            y_val = r * row_step
            fig.add_shape(
                type="line",
                x0=0,
                y0=y_val,
                x1=width,
                y1=y_val,
                line=dict(color="rgba(76, 175, 80, 0.15)", width=1, dash="dot"),
                layer="below",
            )

    # 2. Field Boundary (m)
    fig.add_trace(
        go.Scatter(
            x=[0, width, width, 0, 0],
            y=[0, 0, height, height, 0],
            mode="lines",
            line=dict(color="#2e7d32", dash="solid", width=3),
            name="Field Boundary (m)",
            hoverinfo="skip",
        )
    )

    # 2.1 Master Drone Lawnmower Reconnaissance Flight Path Plan (Zig-Zag sweep)
    sweep_lanes = 6
    x_min, x_max = 8.0, width - 8.0
    y_min, y_max = 8.0, height - 8.0
    lane_gap = (y_max - y_min) / max(1, (sweep_lanes - 1))
    zig_zag_xs, zig_zag_ys = [], []
    for i in range(sweep_lanes):
        y_c = y_min + i * lane_gap
        if i % 2 == 0:
            zig_zag_xs.extend([x_min, x_max])
            zig_zag_ys.extend([y_c, y_c])
        else:
            zig_zag_xs.extend([x_max, x_min])
            zig_zag_ys.extend([y_c, y_c])

    fig.add_trace(
        go.Scatter(
            x=zig_zag_xs,
            y=zig_zag_ys,
            mode="lines",
            line=dict(color="rgba(33, 150, 243, 0.45)", dash="dot", width=1.5),
            name="Master Drone Sweep Plan",
            hoverinfo="skip",
        )
    )

    # 2.2 Corner GPS Geofence Annotations
    import math
    lat0, lon0 = origin_lat_lon or (18.52043, 73.85671)
    dlat = height / 111320.0
    dlon = width / (111320.0 * math.cos(math.radians(lat0)))

    corner_pts = [
        (0.0, 0.0, f"SW: {lat0:.5f}°N, {lon0:.5f}°E", "bottom left"),
        (0.0, height, f"NW: {lat0+dlat:.5f}°N, {lon0:.5f}°E", "top left"),
        (width, height, f"NE: {lat0+dlat:.5f}°N, {lon0+dlon:.5f}°E", "top right"),
        (width, 0.0, f"SE: {lat0:.5f}°N, {lon0+dlon:.5f}°E", "bottom right"),
    ]
    for cx, cy, c_label, c_pos in corner_pts:
        fig.add_trace(
            go.Scatter(
                x=[cx],
                y=[cy],
                mode="markers+text",
                marker=dict(symbol="circle", size=8, color="#00e676", line=dict(width=1.5, color="#000000")),
                text=[c_label],
                textposition=c_pos,
                textfont=dict(size=9, color="#212121"),
                showlegend=False,
                name="GPS Boundary Point",
                hoverinfo="text",
            )
        )

    # 3. Base Station Marker
    fig.add_trace(
        go.Scatter(
            x=[base[0]],
            y=[base[1]],
            mode="markers+text",
            marker=dict(symbol="square", size=16, color="#212121", line=dict(width=2, color="#ffeb3b")),
            text=["🏠 Base Station"],
            textposition="bottom right",
            name="Base Station",
            hovertemplate="<b>Base Station / GCS Launchpad</b><br>X: %{x:.1f} m<br>Y: %{y:.1f} m<extra></extra>",
        )
    )

    # 4. Drone trails up to frame_idx
    trails: Dict[int, List[tuple[float, float]]] = {}
    for f in recording.frames[: idx + 1]:
        for d in f.drones:
            if d.id not in trails:
                trails[d.id] = []
            trails[d.id].append((d.x, d.y))

    for d_id, path in trails.items():
        if path:
            xs, ys = zip(*path)
            d_color = DRONE_PALETTE[d_id % len(DRONE_PALETTE)]
            d_name = "Master Drone (D0)" if d_id == 0 else f"Drone {d_id}"
            fig.add_trace(
                go.Scatter(
                    x=list(xs),
                    y=list(ys),
                    mode="lines",
                    line=dict(color=d_color, width=2.5),
                    opacity=0.6,
                    name=f"{d_name} Trail",
                    hoverinfo="skip",
                )
            )

    # 5. Tasks / Anomalies coloured by owning drone, sized by priority
    scenario_tasks = {t["id"]: t for t in recording.scenario.get("tasks", [])}
    for tf in frame.tasks:
        orig = scenario_tasks.get(tf.id)
        if not orig:
            continue
        x, y = orig["position"]
        prio = float(orig.get("priority", 0.5))
        status = tf.status
        owner_id = tf.drone_id

        # Determine task color based on owning drone
        if owner_id is not None and status in ("ASSIGNED", "IN_PROGRESS", "COMPLETED"):
            task_color = DRONE_PALETTE[owner_id % len(DRONE_PALETTE)]
        else:
            task_color = TASK_STATUS_COLORS.get(status, "#ff9800")

        # Size by priority
        marker_size = 14 + int(prio * 18)
        anomaly_type = ANOMALY_LABELS[tf.id % len(ANOMALY_LABELS)]

        # Visual states:
        # Pending: outlined
        # In progress: highlighted with glowing sensor beam
        # Completed: dimmed with a tick
        if status == "COMPLETED":
            marker_symbol = "circle"
            marker_line = dict(width=2, color="#2e7d32")
            opacity = 0.55
            label_text = f"T{tf.id} ✓"
        elif status == "IN_PROGRESS":
            marker_symbol = "circle"
            marker_line = dict(width=3, color="#ffffff")
            opacity = 1.0
            label_text = f"T{tf.id} (Scanning)"
            # Glowing sensor circle
            fig.add_shape(
                type="circle",
                xref="x",
                yref="y",
                x0=x - 6.0,
                y0=y - 6.0,
                x1=x + 6.0,
                y1=y + 6.0,
                fillcolor="rgba(156, 39, 176, 0.28)",
                line=dict(color="#9c27b0", width=2, dash="dot"),
                layer="below",
            )
        elif status == "ASSIGNED":
            marker_symbol = "circle"
            marker_line = dict(width=2.5, color=task_color)
            opacity = 0.95
            label_text = f"T{tf.id}"
        elif status == "UNREACHABLE":
            marker_symbol = "circle-open"
            marker_line = dict(width=3, color="#f44336")
            opacity = 0.8
            label_text = f"T{tf.id} [X]"
        else:  # PENDING
            marker_symbol = "circle-open"
            marker_line = dict(width=2.5, color="#ff9800")
            opacity = 0.9
            label_text = f"T{tf.id}"

        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers+text",
                marker=dict(
                    symbol=marker_symbol,
                    size=marker_size,
                    color=task_color,
                    opacity=opacity,
                    line=marker_line,
                ),
                text=[label_text],
                textposition="top center",
                textfont=dict(size=10, color="#111111"),
                name=f"Task {tf.id} ({status})",
                showlegend=False,
                hovertemplate=(
                    f"<b>Task {tf.id} — {anomaly_type}</b><br>"
                    f"Status: <b>{status}</b><br>"
                    f"Position: ({x:.1f} m, {y:.1f} m)<br>"
                    f"Priority Score: {prio:.2f}<br>"
                    f"Assigned Drone: {f'Drone {owner_id}' if owner_id is not None else 'Unassigned (Pending)'}<extra></extra>"
                ),
            )
        )

    # 6. Dashed line from each travelling drone to its target
    for d in frame.drones:
        d_color = DRONE_PALETTE[d.id % len(DRONE_PALETTE)]
        if d.status == "TRAVELLING" and d.task_id is not None:
            t_orig = scenario_tasks.get(d.task_id)
            if t_orig:
                tx, ty = t_orig["position"]
                fig.add_trace(
                    go.Scatter(
                        x=[d.x, tx],
                        y=[d.y, ty],
                        mode="lines",
                        line=dict(color=d_color, dash="dash", width=2),
                        name=f"Drone {d.id} Target Vector",
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
        elif d.status == "RETURNING":
            fig.add_trace(
                go.Scatter(
                    x=[d.x, base[0]],
                    y=[d.y, base[1]],
                    mode="lines",
                    line=dict(color=d_color, dash="dot", width=1.8),
                    name=f"Drone {d.id} Return Vector",
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    # 7. Drone Icons and Color Rings at current frame
    drone_icon_size_m = max(8.0, min(14.0, width * 0.09))

    for d in frame.drones:
        d_color = DRONE_PALETTE[d.id % len(DRONE_PALETTE)]
        is_master = (d.id == 0)
        label_title = "Master Drone (D0)" if is_master else f"Drone {d.id}"
        icon_b64 = master_drone_b64 if is_master else swarm_drone_b64

        if d.status == "FAILED":
            # Failed drone: Red X
            fig.add_trace(
                go.Scatter(
                    x=[d.x],
                    y=[d.y],
                    mode="markers+text",
                    marker=dict(symbol="x", size=24, color="#d32f2f", line=dict(width=3, color="#000000")),
                    text=[f"❌ {label_title} (FAILED)"],
                    textposition="bottom center",
                    textfont=dict(size=11, color="#d32f2f"),
                    name=f"Drone {d.id} (FAILED)",
                    hovertemplate=(
                        f"<b>{label_title} [FAILED]</b><br>"
                        f"Position: ({d.x:.1f} m, {d.y:.1f} m)<br>"
                        f"Status: HARD_FAILURE (Tasks released)<br>"
                        f"Energy: {d.energy:.1f} EU<extra></extra>"
                    ),
                )
            )
        else:
            # Active Drone Icon Overlay
            if icon_b64:
                fig.add_layout_image(
                    dict(
                        source=icon_b64,
                        xref="x",
                        yref="y",
                        x=d.x,
                        y=d.y,
                        sizex=drone_icon_size_m,
                        sizey=drone_icon_size_m,
                        xanchor="center",
                        yanchor="middle",
                        layer="above",
                    )
                )

            # Colored Ring Marker & Label
            fig.add_trace(
                go.Scatter(
                    x=[d.x],
                    y=[d.y],
                    mode="markers+text",
                    marker=dict(
                        symbol="circle-open",
                        size=28,
                        color=d_color,
                        line=dict(width=3, color=d_color),
                    ),
                    text=[f"🚁 {label_title}"],
                    textposition="top center",
                    textfont=dict(size=11, color="#111111"),
                    name=f"Drone {d.id} ({d.status})",
                    hovertemplate=(
                        f"<b>{label_title}</b> ({d.status})<br>"
                        f"Position: ({d.x:.1f} m, {d.y:.1f} m)<br>"
                        f"Remaining Energy: {d.energy:.1f} EU<br>"
                        f"Current Target: {f'Task {d.task_id}' if d.task_id is not None else 'None (Standby)'}<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        title=f"🌾 <b>AgriVyaan Multi-UAV Precision Rescan</b> — Time: {frame.t:.1f} s (Step {idx + 1}/{len(recording.frames)})",
        xaxis=dict(
            title="Field Easting X (metres)",
            range=[-5, width + 5],
            zeroline=False,
            gridcolor="rgba(0,0,0,0.08)",
            scaleanchor="y",
            scaleratio=1,
        ),
        yaxis=dict(
            title="Field Northing Y (metres)",
            range=[-5, height + 5],
            zeroline=False,
            gridcolor="rgba(0,0,0,0.08)",
        ),
        plot_bgcolor="#f9fafb" if not farm_image_b64 else "rgba(0,0,0,0)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=50, b=80),
        height=660,
    )

    return fig


def build_comparison_barchart(comparison_df: pd.DataFrame) -> go.Figure:
    """Build grouped bar chart comparing drone counts across makespan and energy."""
    fig = go.Figure()

    conditions = comparison_df["condition"].unique()
    for cond in conditions:
        sub = comparison_df[comparison_df["condition"] == cond]
        fig.add_trace(
            go.Bar(
                name=f"{cond} — Makespan (s)",
                x=[f"{d} Drone(s)" for d in sub["drones"]],
                y=sub["makespan_mean"],
                error_y=dict(type="data", array=sub["makespan_std"]),
                text=[f"{v:.1f}s" for v in sub["makespan_mean"]],
                textposition="auto",
            )
        )

    fig.update_layout(
        title="Mission Completion Makespan by Drone Fleet Size (Mean ± Std)",
        xaxis_title="Fleet Configuration",
        yaxis_title="Makespan (seconds)",
        barmode="group",
        template="plotly_white",
        height=450,
    )
    return fig
