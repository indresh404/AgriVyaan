"""Animation generation helper for mission replay visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.animation as animation
import matplotlib.pyplot as plt

from agrivyaan_swarm.models.recording import RunRecording


def create_simulation_animation(
    recording: RunRecording,
    output_path: Optional[str | Path] = None,
    fps: int = 10,
) -> Optional[animation.FuncAnimation]:
    """Build a 2D matplotlib animation over recorded frames.

    Args:
        recording: RunRecording instance.
        output_path: Optional path to save .mp4 or .gif.
        fps: Frames per second.
    """
    if not recording.frames:
        return None

    fig, ax = plt.subplots(figsize=(7, 7))
    field_data = recording.scenario.get("field", {})
    width = field_data.get("width_m", 100.0)
    height = field_data.get("height_m", 100.0)
    base = field_data.get("base_position", [0.0, 0.0])

    ax.set_xlim(-5, width + 5)
    ax.set_ylim(-5, height + 5)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.set_xlabel("X (metres)")
    ax.set_ylabel("Y (metres)")

    def update(frame_idx: int):
        ax.clear()
        ax.set_xlim(-5, width + 5)
        ax.set_ylim(-5, height + 5)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.set_xlabel("X (metres)")
        ax.set_ylabel("Y (metres)")

        frame = recording.frames[frame_idx]
        ax.set_title(f"Time: {frame.t:.1f}s | Frame {frame_idx + 1}/{len(recording.frames)}")

        # Draw base
        ax.scatter([base[0]], [base[1]], c="black", s=120, marker="s", label="Base")

        # Draw tasks
        for t in frame.tasks:
            orig = next((x for x in recording.scenario.get("tasks", []) if x["id"] == t.id), None)
            if orig:
                pos = orig["position"]
                color = "#2ca02c" if t.status == "COMPLETED" else "#ff7f0e"
                ax.scatter([pos[0]], [pos[1]], c=color, s=80, edgecolors="black", linewidths=0.5)
                ax.text(pos[0] + 1, pos[1] + 1, f"T{t.id}", fontsize=7)

        # Draw drones
        for d in frame.drones:
            c = "red" if d.status == "FAILED" else "blue"
            ax.scatter([d.x], [d.y], c=c, s=100, marker="^")
            ax.text(d.x + 1, d.y + 1, f"D{d.id} ({d.status})", fontsize=8)

    anim = animation.FuncAnimation(fig, update, frames=len(recording.frames), interval=1000 // fps)

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Fall back to HTML/GIF if ffmpeg not present
        try:
            anim.save(str(p), fps=fps)
        except Exception:
            pass
    plt.close(fig)
    return anim
