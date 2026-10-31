"""Static plot generator for simulation reports using Matplotlib Agg backend."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use("Agg")  # Headless backend for CLI and automated testing
import matplotlib.pyplot as plt

from agrivyaan_swarm.models.recording import RunRecording


def plot_simulation_run(
    recording: RunRecording,
    output_path: Optional[str | Path] = None,
    dpi: int = 150,
) -> plt.Figure:
    """Generate a clean 2D summary plot of the simulation mission.

    Displays:
        - Field boundary
        - Base station marker
        - Inspection tasks (colored by final status, sized by priority)
        - Drone trajectories / trails
        - Failed drones marked with a red 'X'
    """
    fig, ax = plt.subplots(figsize=(8, 8))

    field_data = recording.scenario.get("field", {})
    width = field_data.get("width_m", 100.0)
    height = field_data.get("height_m", 100.0)
    base = field_data.get("base_position", [0.0, 0.0])

    # 1. Field boundary
    ax.set_xlim(-5, width + 5)
    ax.set_ylim(-5, height + 5)
    rect = plt.Rectangle((0, 0), width, height, fill=False, edgecolor="gray", linestyle="--", linewidth=1.5, label="Field Boundary")
    ax.add_patch(rect)

    # 2. Base station
    ax.scatter([base[0]], [base[1]], c="black", s=150, marker="s", label="Base Station", zorder=5)

    # 3. Tasks from scenario
    status_colors = {
        "COMPLETED": "#2ca02c",   # Green
        "PENDING": "#ff7f0e",     # Orange
        "ASSIGNED": "#1f77b4",    # Blue
        "IN_PROGRESS": "#9467bd", # Purple
        "UNREACHABLE": "#d62728", # Red
    }

    tasks = recording.scenario.get("tasks", [])
    for task in tasks:
        tid = task.get("id")
        x, y = task.get("position", [0, 0])
        status = task.get("status", "PENDING")
        prio = task.get("priority", 0.5)
        color = status_colors.get(status, "#7f7f7f")
        size = 50 + prio * 100

        ax.scatter([x], [y], c=color, s=size, alpha=0.85, edgecolors="black", linewidths=0.5, zorder=3)
        ax.text(x + 1.0, y + 1.0, f"T{tid}", fontsize=8, alpha=0.8)

    # 4. Drone trajectories from recording frames
    drone_trails: dict[int, list[tuple[float, float]]] = {}
    drone_final_status: dict[int, str] = {}
    drone_colors = ["#1f77b4", "#e377c2", "#17becf", "#bcbd22"]

    for frame in recording.frames:
        for d in frame.drones:
            if d.id not in drone_trails:
                drone_trails[d.id] = []
            drone_trails[d.id].append((d.x, d.y))
            drone_final_status[d.id] = d.status

    for d_id, coords in drone_trails.items():
        if not coords:
            continue
        xs, ys = zip(*coords)
        color = drone_colors[d_id % len(drone_colors)]
        ax.plot(xs, ys, color=color, alpha=0.6, linewidth=1.8, label=f"Drone {d_id} Trail")

        # Mark final position
        final_x, final_y = xs[-1], ys[-1]
        if drone_final_status.get(d_id) == "FAILED":
            ax.scatter([final_x], [final_y], c="red", s=200, marker="X", zorder=6, label=f"Drone {d_id} (FAILED)")
        else:
            ax.scatter([final_x], [final_y], c=color, s=80, marker="o", zorder=4)

    ax.set_title(
        f"AgriVyaan Swarm Run: {recording.run_id}\n"
        f"Makespan: {recording.metrics.get('makespan_s', 0)}s | Coverage: {recording.metrics.get('priority_weighted_coverage', 0)}",
        fontsize=11,
    )
    ax.set_xlabel("X (metres)")
    ax.set_ylabel("Y (metres)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8)
    fig.tight_layout()

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=dpi)

    return fig
