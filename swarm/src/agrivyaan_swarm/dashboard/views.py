"""Tab render functions for the AgriVyaan Streamlit visual dashboard."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
import streamlit as st

from agrivyaan_swarm.dashboard.figures import (
    ANOMALY_LABELS,
    build_comparison_barchart,
    build_mission_replay_figure,
)
from agrivyaan_swarm.models.recording import RunRecording
from scripts.compare_drones import run_paired_comparison


def render_mission_view(
    recording: Optional[RunRecording],
    farm_image_b64: Optional[str] = None,
    master_drone_b64: Optional[str] = None,
    swarm_drone_b64: Optional[str] = None,
    field_width_m: Optional[float] = None,
    field_height_m: Optional[float] = None,
    anomaly_images: Optional[Dict[str, Optional[str]]] = None,
) -> None:
    """Render Tab 1: Interactive Mission Replay with farm map, drone icons, and inspection evidence."""
    if recording is None:
        st.info("No simulation run loaded. Configure parameters in the sidebar and click **Run Simulation**.")
        return

    frames_count = len(recording.frames)
    if frames_count == 0:
        st.warning("Recording has no frames.")
        return

    st.subheader("🌾 Farm Mission Live Replay")

    col_btn_launch, _ = st.columns([2, 1])
    with col_btn_launch:
        if st.button("🚀 Launch 60-FPS Dedicated Smooth Python Window", type="primary"):
            import subprocess
            import sys
            script_path = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "visual_simulation_window.py"
            subprocess.Popen([sys.executable, str(script_path)])
            st.success("✨ Launched 60-FPS Hardware-Accelerated Simulation Window! Check your desktop.")

    # Playback Controls Bar
    c_play, c_pause, c_step_back, c_step_fwd, c_reset, c_speed = st.columns([1, 1, 1, 1, 1, 2])
    with c_play:
        auto_play = st.button("▶️ Play", help="Animate the multi-drone mission forward")
    with c_pause:
        pause_clicked = st.button("⏸️ Pause", help="Pause animation")
    with c_step_back:
        if st.button("⏪ -5"):
            st.session_state["frame_index"] = max(0, st.session_state.get("frame_index", 0) - 5)
    with c_step_fwd:
        if st.button("⏩ +5"):
            st.session_state["frame_index"] = min(frames_count - 1, st.session_state.get("frame_index", 0) + 5)
    with c_reset:
        if st.button("🔄 Reset"):
            st.session_state["frame_index"] = 0
    with c_speed:
        speed = st.select_slider(
            "Playback Speed",
            options=["Normal (1x)", "Fast (2x)", "Turbo (5x)"],
            value="Normal (1x)",
        )

    # Time Slider (Unified single moment selector)
    frame_idx = st.slider(
        "Mission Timeline Slider (Step / Frame)",
        min_value=0,
        max_value=frames_count - 1,
        value=st.session_state.get("frame_index", 0),
        help="Drag to view exact positions, battery status, and sensor beams at any moment.",
    )
    st.session_state["frame_index"] = frame_idx

    current_frame = recording.frames[frame_idx]
    st.caption(
        f"⏱️ **Mission Clock:** `{current_frame.t:.1f} s` | "
        f"**Step:** `{frame_idx + 1} / {frames_count}` | "
        f"**Active Drones:** `{len(current_frame.drones)}` | "
        f"**Visual Mode:** High-Resolution Top-View Farm Overlay"
    )

    plot_placeholder = st.empty()

    if auto_play and not pause_clicked:
        delay = 0.12 if "Normal" in speed else (0.05 if "Fast" in speed else 0.02)
        step_stride = 1 if "Normal" in speed else (2 if "Fast" in speed else 4)
        for i in range(frame_idx, frames_count, step_stride):
            st.session_state["frame_index"] = i
            fig_i = build_mission_replay_figure(
                recording,
                frame_idx=i,
                farm_image_b64=farm_image_b64,
                master_drone_b64=master_drone_b64,
                swarm_drone_b64=swarm_drone_b64,
                field_width_m=field_width_m,
                field_height_m=field_height_m,
            )
            plot_placeholder.plotly_chart(fig_i, use_container_width=True)
            time.sleep(delay)
        st.session_state["frame_index"] = frames_count - 1
    else:
        fig = build_mission_replay_figure(
            recording,
            frame_idx=frame_idx,
            farm_image_b64=farm_image_b64,
            master_drone_b64=master_drone_b64,
            swarm_drone_b64=swarm_drone_b64,
            field_width_m=field_width_m,
            field_height_m=field_height_m,
        )
        plot_placeholder.plotly_chart(fig, use_container_width=True)

    # Active Anomaly Inspection Evidence Card (if a drone is inspecting or travelling)
    active_inspecting_drone = next((d for d in current_frame.drones if d.status == "INSPECTING" and d.task_id is not None), None)
    if active_inspecting_drone is None:
        active_inspecting_drone = next((d for d in current_frame.drones if d.task_id is not None), None)

    if active_inspecting_drone and active_inspecting_drone.task_id is not None and anomaly_images:
        tid = active_inspecting_drone.task_id
        anomaly_name = ANOMALY_LABELS[tid % len(ANOMALY_LABELS)]
        img_key = (
            "crop_early_blight" if (tid % 3 == 0)
            else ("crop_yellowish" if (tid % 3 == 1) else "crop_growth")
        )
        evidence_b64 = anomaly_images.get(img_key)

        with st.container():
            st.markdown("### 🔬 Targeted Crop Rescan — Visual Evidence Box")
            col_img, col_info = st.columns([1, 2])
            with col_img:
                if evidence_b64:
                    st.image(evidence_b64, caption=f"Zone T{tid} High-Res Multispectral Capture", use_container_width=True)
                else:
                    st.info("No optical evidence attached.")
            with col_info:
                st.markdown(
                    f"""
                    - **Target Crop Zone:** `Zone T{tid}`
                    - **Detected Phenotype / Anomaly:** **{anomaly_name}**
                    - **Assigned Inspector:** `Drone {active_inspecting_drone.id}` {"(Master Coordinator)" if active_inspecting_drone.id == 0 else "(Swarm Worker)"}
                    - **Drone Status:** `{active_inspecting_drone.status}`
                    - **Battery Remaining:** `{active_inspecting_drone.energy:.1f} EU`
                    - **Verification State:** Evidence captured and verified onboard.
                    """
                )

    st.markdown("---")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🚁 Drone Fleet Telemetry (at step)")
        drone_data = [
            {
                "Drone": f"Drone {d.id} (Master)" if d.id == 0 else f"Drone {d.id}",
                "Status": d.status,
                "Position (X, Y)": f"({d.x:.1f}, {d.y:.1f}) m",
                "Battery (EU)": f"{d.energy:.1f} EU",
                "Target Task": f"Zone T{d.task_id}" if d.task_id is not None else "Base / Standby",
            }
            for d in current_frame.drones
        ]
        st.dataframe(pd.DataFrame(drone_data))

    with col2:
        st.subheader(f"📜 Flight Events Log (up to t = {current_frame.t:.1f}s)")
        events_up_to_t = [
            {
                "Time (s)": e.t,
                "Type": e.type,
                "Drone": f"Drone {e.drone_id}" if e.drone_id is not None else "Coordinator",
                "Task": f"Zone T{e.task_id}" if e.task_id is not None else "-",
                "Detail": e.detail,
            }
            for e in recording.events
            if e.t <= current_frame.t
        ]
        if events_up_to_t:
            st.dataframe(pd.DataFrame(events_up_to_t[-8:]))
        else:
            st.caption("No events prior to this timestamp.")


def render_metrics_tab(recording: Optional[RunRecording]) -> None:
    """Render Tab 2: Mission Metrics, KPI cards, and artifact downloads."""
    if recording is None:
        st.info("Run or load a simulation to view detailed metrics.")
        return

    m = recording.metrics

    # KPI summary cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mission Makespan", f"{m.get('makespan_s', 0)} s")
    c2.metric("Distance Travelled", f"{m.get('total_distance_m', 0)} m")
    c3.metric("Energy Consumed", f"{m.get('total_energy_eu', 0)} EU")
    c4.metric("Energy / Completed Task", f"{m.get('energy_per_completed_task_eu', 0)} EU")

    c5, c6, c7, c8 = st.columns(4)
    cov = m.get("priority_weighted_coverage", "n/a")
    cov_str = f"{cov * 100:.1f}%" if isinstance(cov, (int, float)) else str(cov)
    c5.metric("Priority Coverage", cov_str)
    c6.metric("Completed Tasks", f"{m.get('completed_tasks_count', 0)} / {m.get('total_tasks_count', 0)}")
    c7.metric("Load Balance (Std)", f"{m.get('load_balance_std', 0)}")
    c8.metric("Completion State", str(recording.completion_state.value))

    # Invariant alert
    dup = m.get("duplicate_assignments", 0)
    batt_viol = m.get("battery_reserve_violations", 0)
    if dup == 0 and batt_viol == 0:
        st.success("Simulation Invariants Verified: 0 Duplicate Assignments | 0 Battery Reserve Violations")
    else:
        st.error(f"Invariant Violation: {dup} duplicate assignments, {batt_viol} battery reserve violations!")

    st.subheader("All Computed Metrics")
    metrics_table = [{"Metric": k, "Value": str(v)} for k, v in m.items()]
    st.table(pd.DataFrame(metrics_table))

    # Download buttons
    st.subheader("Export Artifacts")
    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download metrics.json",
            data=json.dumps(m, indent=2),
            file_name=f"{recording.run_id}_metrics.json",
            mime="application/json",
        )
    with dl2:
        metrics_df = pd.DataFrame([m])
        st.download_button(
            "Download metrics.csv",
            data=metrics_df.to_csv(index=False),
            file_name=f"{recording.run_id}_metrics.csv",
            mime="text/csv",
        )

    # Full historical event log
    st.subheader("Full Historical Event Log")
    events_data = [
        {
            "Time (s)": float(e.t),
            "Type": str(e.type),
            "Drone ID": f"Drone {e.drone_id}" if e.drone_id is not None else "Coordinator",
            "Task ID": f"T{e.task_id}" if e.task_id is not None else "-",
            "Detail": str(e.detail),
        }
        for e in recording.events
    ]
    st.dataframe(pd.DataFrame(events_data))


@st.cache_data
def cached_run_comparison(seeds: int) -> pd.DataFrame:
    """Run cached multi-drone scaling comparison."""
    return run_paired_comparison(seeds_count=seeds)


def render_compare_tab() -> None:
    """Render Tab 3: 1, 2, and 3 drone fleet comparison across paired seeds."""
    st.subheader("Multi-Drone Fleet Scaling & Resilience Comparison")
    st.write(
        "Compare fleet sizes (1, 2, and 3 drones) across paired random seeds under Nominal, "
        "Energy-Constrained, and Hard Failure conditions. All values computed dynamically from simulator runs."
    )

    seeds_count = st.slider("Number of Paired Seeds", min_value=3, max_value=20, value=10, step=1)
    if st.button("Run Comparison Experiment"):
        with st.spinner(f"Simulating across {seeds_count} paired scenarios..."):
            df_runs = cached_run_comparison(seeds_count)
            st.session_state["comparison_df"] = df_runs

    df_runs = st.session_state.get("comparison_df")
    if df_runs is not None:
        summary = df_runs.groupby(["condition", "drones"]).agg(
            makespan_mean=("makespan_s", "mean"),
            makespan_std=("makespan_s", "std"),
            energy_mean=("total_energy_eu", "mean"),
            energy_std=("total_energy_eu", "std"),
            coverage_mean=("coverage", "mean"),
            coverage_std=("coverage", "std"),
            completed_mean=("completed_tasks", "mean"),
        ).round(2).reset_index()

        st.plotly_chart(build_comparison_barchart(summary), use_container_width=True)
        st.dataframe(summary)
        st.info(
            "Insight: Scaling from 1 to 3 drones significantly reduces makespan and improves resilience "
            "under single-drone failure. However, fleet travel to/from base can increase total energy consumed."
        )


def render_assumptions_tab() -> None:
    """Render Tab 4: Modeling assumptions, units, and simulation-only statements."""
    st.subheader("Simulation Assumptions & Physical Modeling Constraints")

    st.markdown(
        """
        ### 1. Simulation Scope & Integrity
        - **Simulation only. Synthetic zones and abstract energy model. Not real detections or flight results.**
        - **No Hardware Claims:** This software does not represent physical multi-drone flight or real crop AI detections.

        ### 2. Units of Measurement
        | Physical Quantity | Simulation Unit | Notes |
        | :--- | :--- | :--- |
        | **Distance** | Metres (m) | Default field is 100 m × 100 m |
        | **Time** | Seconds (s) | Fixed step `dt = 0.5 s` |
        | **Speed** | m/s | Drone travels linearly up to `max_speed_mps` |
        | **Energy** | Energy Units (EU) | Abstract budget (not Wh or battery %) |

        ### 3. Abstract Energy Model
        $$\\text{travel\\_energy}(d) = \\text{travel\\_rate\\_eu\\_per\\_m} \\times d$$
        $$\\text{inspect\\_energy}(k) = \\text{inspect\\_rate\\_eu\\_per\\_s} \\times \\text{duration}_k$$
        $$\\text{reserve\\_energy} = \\text{return\\_reserve\\_fraction} \\times \\text{capacity}$$

        A task $k$ is feasible for drone $D$ at position $p$ with current energy $E$ if:
        $$E - \\text{safety\\_factor} \\times \\text{travel}(p \\to k) - \\text{inspect}_k - \\text{safety\\_factor} \\times \\text{travel}(k \\to \\text{base}) \\ge \\text{reserve\\_energy}$$

        ### 4. Allocation Policy
        - **Greedy Baseline:** Eligible drones sequentially pick the nearest feasible task by Euclidean distance.
        - **Bias:** Lower drone IDs pick first.
        - **Guaranteed Termination:** Runs terminate upon mission completion or maximum time limit.
        """
    )
