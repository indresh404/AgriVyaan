"""AgriVyaan Visual Swarm Simulation & Replay Dashboard."""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add project root to sys.path so imports work seamlessly
root_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pandas as pd
import streamlit as st

from agrivyaan_swarm.config import FailureConfig, FailureTrigger, load_config
from agrivyaan_swarm.dashboard.assets_loader import (
    get_default_assets,
    image_to_base64_data_uri,
)
from agrivyaan_swarm.dashboard.state import (
    get_current_recording,
    init_session_state,
    list_saved_runs,
    load_run_by_path,
    set_current_recording,
)
from agrivyaan_swarm.dashboard.views import (
    render_assumptions_tab,
    render_compare_tab,
    render_metrics_tab,
    render_mission_view,
)
from agrivyaan_swarm.main import run_simulation
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus
from agrivyaan_swarm.scenario_io import load_scenario_file


def main() -> None:
    st.set_page_config(
        page_title="AgriVyaan Swarm Simulator",
        page_icon="🚁",
        layout="wide",
    )

    init_session_state()

    # Mandatory Simulation Only Notice Banner
    st.warning("Simulation only. Synthetic zones and abstract energy model. Not real detections or flight results.")

    st.title("🚁 AgriVyaan Multi-UAV Precision Rescan Simulator")

    # Load default visual assets from assets/
    default_assets = get_default_assets("assets")

    # Sidebar: Simulation & Asset Controls
    st.sidebar.header("Mission & Farm Configuration")

    # 1. Field Dimensions in Metres (Maps image directly to 0..W, 0..H)
    st.sidebar.subheader("📐 Field Dimensions (Metres)")
    col_w, col_h = st.sidebar.columns(2)
    field_width = col_w.number_input("Width (m)", min_value=20.0, max_value=1000.0, value=100.0, step=10.0)
    field_height = col_h.number_input("Height (m)", min_value=20.0, max_value=1000.0, value=100.0, step=10.0)

    # 2. Farm Map & Visual Layers (Crop imagery only - no satellite)
    st.sidebar.subheader("🌱 Crop Field Visual Imagery")
    farm_map_choice = st.sidebar.radio(
        "Map Background Source",
        ["High-Res Aerial Crop Photo", "Upload Custom Farm Map", "Plain Grid"],
    )

    farm_b64: str | None = None
    if farm_map_choice == "High-Res Aerial Crop Photo":
        farm_b64 = default_assets.get("crop_image")
    elif farm_map_choice == "Upload Custom Farm Map":
        uploaded_map = st.sidebar.file_uploader(
            "Upload Crop Field Image (PNG / JPG)",
            type=["png", "jpg", "jpeg"],
            help="Upload an aerial crop photo to scale across 0..W, 0..H metres.",
        )
        if uploaded_map:
            farm_b64 = image_to_base64_data_uri(uploaded_map.read(), mime_type=uploaded_map.type or "image/png")
            if farm_b64:
                st.sidebar.success("Custom crop image loaded!")
            else:
                st.sidebar.error("Failed to parse image file. Falling back to default.")

    # 3. Drone Height & Camera Footprint
    st.sidebar.subheader("📏 Flight Altitude & Optical Footprint")
    scout_alt = st.sidebar.slider("Scout Drone Altitude (m)", min_value=10.0, max_value=60.0, value=25.0, step=2.5)
    detail_alt = st.sidebar.slider("Investigation Drone Altitude (m)", min_value=5.0, max_value=25.0, value=12.0, step=1.0)
    # Footprint calculation
    fov_x_rad = 1.134  # ~65 deg
    fov_y_rad = 0.873  # ~50 deg
    footprint_w = 2.0 * scout_alt * math.tan(fov_x_rad / 2.0)
    footprint_h = 2.0 * scout_alt * math.tan(fov_y_rad / 2.0)
    st.sidebar.caption(f"📐 Ground Footprint at {scout_alt:.1f}m: **{footprint_w:.1f}m × {footprint_h:.1f}m** ({footprint_w*footprint_h:.0f} m²)")

    # 4. Swarm Fleet Controls (Up to 10 Drones)
    st.sidebar.subheader("🚁 Fleet Parameters (1-10 Drones)")
    drones_count = st.sidebar.slider("Number of Virtual Drones", min_value=1, max_value=10, value=3)
    seed = st.sidebar.number_input("RNG Seed", min_value=1, max_value=99999, value=42)
    task_count = st.sidebar.slider("Number of Candidate Zones", min_value=1, max_value=30, value=10)
    random_low_batt = st.sidebar.checkbox("Random Initial Low Battery Scenarios", value=True, help="Randomly sets 1-2 drones to 20-30% battery.")
    allocator_type = st.sidebar.selectbox("Allocation Policy", ["Greedy Nearest-Task (Sequential ID)"])

    # 5. Fault Injection Toggle
    st.sidebar.subheader("⚠️ Fault Injection")
    enable_failure = st.sidebar.checkbox("Inject Drone Failure Event", value=False)
    failure_configs = []
    if enable_failure:
        fail_drone_id = st.sidebar.selectbox("Target Drone ID", list(range(int(drones_count))))
        fail_kind = st.sidebar.selectbox("Failure Kind", ["HARD_FAILURE", "COMM_LOSS"])
        fail_time = st.sidebar.number_input("Trigger Time (s)", min_value=0.0, max_value=300.0, value=30.0, step=5.0)
        fail_delay = st.sidebar.number_input("Detection Delay (s)", min_value=0.0, max_value=60.0, value=5.0, step=1.0)
        failure_configs.append(
            FailureConfig(
                drone_id=int(fail_drone_id),
                trigger=FailureTrigger(type="time", t=float(fail_time)),
                kind=fail_kind,
                detection_delay_s=float(fail_delay),
            )
        )

    # Prepare Config
    config = load_config("config/default.json")
    config.field.width_m = float(field_width)
    config.field.height_m = float(field_height)
    config.drones.count = int(drones_count)
    config.simulation.seed = int(seed)
    config.tasks.count = int(task_count)
    config.failures = failure_configs

    # Run Simulation Trigger
    if st.sidebar.button("🚀 Run Simulation", type="primary"):
        with st.spinner("Executing multi-drone coordination simulation..."):
            rec = run_simulation(config)
            set_current_recording(rec)
            st.success(f"Simulation completed with state: **{rec.completion_state.value}**")

    # Load Previously Saved Simulation
    st.sidebar.markdown("---")
    st.sidebar.subheader("📂 Load Saved Run")
    saved_runs = list_saved_runs()
    if saved_runs:
        selected_run = st.sidebar.selectbox("Select Run ID", [p.parent.name for p in saved_runs])
        if st.sidebar.button("Load Recording"):
            matched_path = next((p for p in saved_runs if p.parent.name == selected_run), None)
            if matched_path:
                load_run_by_path(matched_path)
                st.sidebar.success(f"Loaded {selected_run}")

    # Ensure a default simulation is loaded on initial startup
    if get_current_recording() is None:
        init_rec = run_simulation(config)
        set_current_recording(init_rec)

    # Dashboard Tabs (Exactly 4 Tabs Total)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📍 Mission View",
        "📊 Metrics",
        "📈 Compare",
        "ℹ️ Assumptions",
    ])

    rec = get_current_recording()

    master_drone_b64 = default_assets.get("master_drone")
    swarm_drone_b64 = default_assets.get("swarm_drone")

    with tab1:
        render_mission_view(
            recording=rec,
            farm_image_b64=farm_b64,
            master_drone_b64=master_drone_b64,
            swarm_drone_b64=swarm_drone_b64,
            field_width_m=float(field_width),
            field_height_m=float(field_height),
            anomaly_images=default_assets,
        )

    with tab2:
        render_metrics_tab(rec)

    with tab3:
        render_compare_tab()

    with tab4:
        render_assumptions_tab()


if __name__ == "__main__":
    main()
