"""Tests for the standalone visual simulation window and phased mission workflow."""

import os
import sys
from pathlib import Path

# Fix Windows Python virtualenv TCL/TK paths if not configured
if sys.platform.startswith("win"):
    base_tcl = Path(sys.base_prefix) / "tcl"
    tcl_dir = base_tcl / "tcl8.6"
    tk_dir = base_tcl / "tk8.6"
    if tcl_dir.exists() and "TCL_LIBRARY" not in os.environ:
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir.exists() and "TK_LIBRARY" not in os.environ:
        os.environ["TK_LIBRARY"] = str(tk_dir)

import pytest
import tkinter as tk
from scripts.visual_simulation_window import AgriVyaanSimulationApp, metres_to_gps


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_visual_simulation_app_initialization(tk_root):
    """Verify visual simulation window initializes, generates waypoints, and updates steps cleanly."""
    app = AgriVyaanSimulationApp(tk_root)
    assert app.master_drone is not None
    assert app.master_drone.is_master is True
    assert len(app.swarm_drones) == 2
    assert len(app.lawnmower_waypoints) > 0
    assert len(app.anomalies) > 0

    # Step simulation forward
    app.update_simulation(dt=0.1)
    assert app.sim_time > 0.0

    # Test failure injection
    app.inject_drone_failure()
    assert app.swarm_drones[0].status == "FAILED"


def test_gps_coordinate_mapping():
    """Verify conversion of local coordinates to GPS lat/lon."""
    lat, lon = metres_to_gps(0.0, 0.0)
    assert lat == 18.52043
    assert lon == 73.85671

    lat_ne, lon_ne = metres_to_gps(100.0, 100.0)
    assert lat_ne > lat
    assert lon_ne > lon


def test_phased_mission_workflow(tk_root):
    """Verify Master Drone scouts first while Swarm Drones wait in STANDBY at base."""
    app = AgriVyaanSimulationApp(tk_root)
    assert app.mission_phase == 0  # Phase 0: Standby / Setup
    assert app.master_drone.status == "STANDBY"

    # Start mission
    app.start_mission()
    assert app.mission_phase == 1  # Phase 1: Master Scouting
    assert app.master_drone.status == "SCANNING"

    # Step through Phase 1
    app.update_simulation(dt=1.0)
    assert app.mission_phase == 1

    # Swarm drones must remain in STANDBY during Master Drone scouting!
    for d in app.swarm_drones:
        assert d.status == "STANDBY"


def test_three_node_types_and_post_process_heatmap(tk_root):
    """Verify manual placement of 3 node types and dynamic post-process heatmap generation."""
    app = AgriVyaanSimulationApp(tk_root)

    # 1. Verify clean satellite map in Step 1 (no early heatmap)
    app.set_wizard_step(1)
    assert len(app.covered_cells) == 0

    # 2. Step 2: Manually place 1 Yellowish, 1 Growth, and 1 Disease node
    app.set_wizard_step(2)
    app.clear_nodes()
    assert len(app.anomalies) == 0

    class MockClick:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    # Place Yellowish Node
    app.select_place_node_type("yellowish")
    app.on_canvas_click(MockClick(120, 120))
    assert len(app.anomalies) == 1
    assert app.anomalies[0].type_key == "yellowish"
    assert app.anomalies[0].file == "crop_yellowish.jpeg"

    # Place Growth Node
    app.select_place_node_type("growth")
    app.on_canvas_click(MockClick(240, 240))
    assert len(app.anomalies) == 2
    assert app.anomalies[1].type_key == "growth"
    assert app.anomalies[1].file == "crop_growth.jpeg"

    # Place Disease Node
    app.select_place_node_type("disease")
    app.on_canvas_click(MockClick(360, 360))
    assert len(app.anomalies) == 3
    assert app.anomalies[2].type_key == "disease"
    assert app.anomalies[2].file == "crop_early_blight.jpeg"

    # 3. In Step 5, start simulation: Heatmap generates as drone flies
    app.set_wizard_step(5)
    app.start_mission()
    app.update_simulation(dt=1.5)
    assert len(app.covered_cells) > 0


def test_map_zoom_pan_and_scale(tk_root):
    """Verify map zoom in/out, panning, scale rendering, and coordinate reversibility."""
    app = AgriVyaanSimulationApp(tk_root)

    # 1. Initial State
    assert app.zoom_level == 1.0
    assert app.pan_x == 0.0
    assert app.pan_y == 0.0

    # 2. Test Zoom In / Out
    app.zoom_by(1.25)
    assert round(app.zoom_level, 2) == 1.25

    app.zoom_by(0.80)
    assert round(app.zoom_level, 2) == 1.00

    # Test clamping limits (0.4x to 5.0x)
    app.zoom_by(10.0)
    assert app.zoom_level == 5.0
    app.zoom_by(0.01)
    assert app.zoom_level == 0.40

    # Reset
    app.reset_zoom()
    assert app.zoom_level == 1.0
    assert app.pan_x == 0.0
    assert app.pan_y == 0.0

    # 3. Test Fit to Field
    app.fit_to_field()
    assert 0.5 <= app.zoom_level <= 4.0

    # 4. Test Coordinate Transformation Invariance under arbitrary Zoom & Pan
    test_points = [(15.0, 15.0), (50.0, 50.0), (85.0, 85.0)]
    for zoom in [0.75, 1.0, 1.5, 2.0]:
        app.zoom_level = zoom
        app.pan_x = 24.0
        app.pan_y = -18.0
        for xm, ym in test_points:
            cx, cy = app.metres_to_canvas(xm, ym)
            rx, ry = app.canvas_to_metres(cx, cy)
            assert abs(rx - xm) <= 0.1
            assert abs(ry - ym) <= 0.1

    # 5. Test Mode Toggles (Edit vs Pan)
    app.set_tool_mode("pan")
    assert app.active_tool_mode == "pan"
    app.set_tool_mode("edit")
    assert app.active_tool_mode == "edit"

    # 6. Test Scale and Compass Drawing
    app.render_map_scale()
    app.render_compass_rose()


def test_crop_only_and_altitude_zones(tk_root):
    """Verify satellite is eliminated, crop background is active, and altitude scales footprint and square zones."""
    app = AgriVyaanSimulationApp(tk_root)

    # 1. Verify crop background only (no satellite)
    assert app.active_farm_source == "crop_image.png"

    # 2. Verify camera footprint calculation
    fw_25, fh_25 = app.calculate_camera_footprint(25.0)
    fw_40, fh_40 = app.calculate_camera_footprint(40.0)
    assert fw_40 > fw_25
    assert fh_40 > fh_25

    # 3. Verify square zones scale with altitude
    app.scout_altitude_m = 15.0
    app.generate_square_zones()
    zone_sz_15 = app.active_zone_size_m
    count_15 = len(app.square_zones)

    app.scout_altitude_m = 40.0
    app.generate_square_zones()
    zone_sz_40 = app.active_zone_size_m
    count_40 = len(app.square_zones)

    assert zone_sz_40 > zone_sz_15
    assert count_15 >= count_40  # Higher altitude = larger zones = fewer zones to cover same field

    # 4. Verify on_altitude_changed updates altitude and draws footprint
    app.on_altitude_changed("35.0")
    assert app.scout_altitude_m == 35.0
    app.render_drone_footprint_coverage()


def test_two_stage_detection_and_node_sizes(tk_root):
    """Verify node sizing, Master Scout discovers Yellowish/Brown candidates only, and Swarm classifies Disease."""
    app = AgriVyaanSimulationApp(tk_root)
    app.set_wizard_step(2)
    app.clear_nodes()

    # 1. Place Yellowish (Small), Brown (Medium), and Disease (Large)
    class MockClick:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    app.select_place_node_type("yellowish")
    app.select_place_node_size("small")
    app.on_canvas_click(MockClick(200, 200))
    assert app.anomalies[-1].size_key == "small"
    assert app.anomalies[-1].radius_m == 6.0

    app.select_place_node_type("growth")  # Brown (Stunted)
    app.select_place_node_size("medium")
    app.on_canvas_click(MockClick(300, 300))
    assert app.anomalies[-1].size_key == "medium"
    assert app.anomalies[-1].radius_m == 12.0

    app.select_place_node_type("disease")
    app.select_place_node_size("large")
    app.on_canvas_click(MockClick(400, 400))
    assert app.anomalies[-1].size_key == "large"
    assert app.anomalies[-1].radius_m == 20.0

    # 2. Stage A: Master Scout detects Yellowish & Brown, flagging as candidates
    app.set_wizard_step(5)
    app.start_mission()
    assert app.mission_phase == 1

    # Position Master drone right over Yellowish node
    app.master_drone.x = app.anomalies[0].x
    app.master_drone.y = app.anomalies[0].y
    app.update_simulation(dt=0.1)

    assert app.anomalies[0].is_candidate is True
    assert app.anomalies[0].inspected is False  # Not inspected yet!

    # 3. Stage B: Swarm inspection verifies and classifies pathology
    app.mission_phase = 2
    for d in app.swarm_drones:
        d.status = "IDLE"

    app.update_simulation(dt=0.1)
    assigned_drone = next((d for d in app.swarm_drones if d.current_task_id == app.anomalies[0].id), None)
    assert assigned_drone is not None


def test_fleet_up_to_10_and_collision_avoidance(tk_root):
    """Verify fleet scaling to 10 drones, low battery handling, and safe separation collision checks."""
    app = AgriVyaanSimulationApp(tk_root)

    # 1. Fleet scaling up to 10 drones
    app.num_swarm_drones = 9  # 1 Master + 9 Swarm = 10 Total
    app.reset_simulation()
    assert len(app.swarm_drones) == 9
    assert app.master_drone.is_master is True
    assert len(app.swarm_drones) + 1 == 10

    # 2. Collision avoidance check
    d1 = app.swarm_drones[0]
    d2 = app.swarm_drones[1]
    d1.status = "TRAVELLING"
    d2.status = "TRAVELLING"
    d1.x, d1.y = 50.0, 50.0

    # Test moving d2 within 3 metres of d1 (< 6.0m safe separation)
    can_move = app.check_collision_avoidance(d2, 52.0, 50.0)
    assert can_move is False
    assert d2.holding_position is True

    # Test moving d2 to safe distance (15m away)
    can_move_safe = app.check_collision_avoidance(d2, 65.0, 50.0)
    assert can_move_safe is True
    assert d2.holding_position is False

    # 3. Heatmap toggle
    assert app.heatmap_enabled is True
    app.toggle_heatmap()
    assert app.heatmap_enabled is False
    app.toggle_heatmap()
    assert app.heatmap_enabled is True


def test_battery_aware_shortest_path_and_multi_drone_collaboration(tk_root):
    """Verify battery-aware shortest-path allocation and simultaneous multi-drone collaboration."""
    app = AgriVyaanSimulationApp(tk_root)
    app.num_swarm_drones = 4
    app.reset_simulation()
    assert len(app.swarm_drones) == 4

    # Setup 3 candidate nodes
    app.anomalies[0].is_candidate = True
    app.anomalies[0].x, app.anomalies[0].y = 15.0, 15.0  # Close to base

    app.anomalies[1].is_candidate = True
    app.anomalies[1].x, app.anomalies[1].y = 45.0, 45.0  # Mid field

    app.anomalies[2].is_candidate = True
    app.anomalies[2].x, app.anomalies[2].y = 85.0, 85.0  # Far field

    # Give Drone 1 full battery (500 Wh), Drone 2 full battery (500 Wh), Drone 3 critically low battery (60 Wh)
    app.swarm_drones[0].battery_eu = 500.0
    app.swarm_drones[0].status = "IDLE"

    app.swarm_drones[1].battery_eu = 500.0
    app.swarm_drones[1].status = "IDLE"

    app.swarm_drones[2].battery_eu = 45.0  # Below 50 Wh reserve limit!
    app.swarm_drones[2].status = "IDLE"

    # Test energy cost calculation
    total_dist, est_energy, is_feasible = app.calculate_mission_energy_cost(app.swarm_drones[0], app.anomalies[0])
    assert total_dist > 0.0
    assert est_energy > 0.0
    assert is_feasible is True

    # Infeasible for Drone 3 due to low battery
    _, _, d3_feasible = app.calculate_mission_energy_cost(app.swarm_drones[2], app.anomalies[2])
    assert d3_feasible is False

    # Execute collaborative battery-aware shortest-path allocation
    app.allocate_tasks_battery_aware()

    # Drone 3 must be flagged LOW_BATTERY and NOT assigned any candidate
    assert app.swarm_drones[2].status == "LOW_BATTERY"
    assert app.swarm_drones[2].current_task_id is None

    # Healthy drones 1 and 2 must be dispatched together simultaneously!
    assert app.swarm_drones[0].status == "TRAVELLING"
    assert app.swarm_drones[1].status == "TRAVELLING"
    assert app.swarm_drones[0].current_task_id is not None
    assert app.swarm_drones[1].current_task_id is not None
    assert app.swarm_drones[0].current_task_id != app.swarm_drones[1].current_task_id

    # Verify shortest-path collaborative allocation:
    assigned_tasks = {app.swarm_drones[0].current_task_id, app.swarm_drones[1].current_task_id}
    assert app.anomalies[0].id in assigned_tasks  # Closest candidate assigned to closest available drone!


def test_proper_yellow_heatmap_rendering(tk_root):
    """Verify dual-tone agricultural greenery and golden-yellow chlorosis stress heatmap renders smoothly."""
    app = AgriVyaanSimulationApp(tk_root)
    app.set_wizard_step(5)
    app.heatmap_enabled = True

    # Seed covered cells
    app.covered_cells = {(x, y) for x in range(10, 30) for y in range(10, 30)}
    # Discover Yellowish anomaly
    app.anomalies[0].discovered = True
    app.anomalies[0].is_candidate = True

    # Render canvas with heatmap and verify zero errors
    app.render_canvas()
    dynamic_items = app.canvas.find_withtag("dynamic")
    assert len(dynamic_items) > 0


def test_stage_b_multi_drone_collaborative_workflow_after_master(tk_root):
    """Verify Master Drone completes survey first, then multiple swarm drones launch together in Stage B."""
    app = AgriVyaanSimulationApp(tk_root)
    app.num_swarm_drones = 3
    app.set_wizard_step(5)
    app.start_mission()

    # In Stage 1: Master Drone is scanning, all Swarm Drones MUST be in STANDBY at base
    assert app.mission_phase == 1
    assert app.master_drone.status == "SCANNING"
    for d in app.swarm_drones:
        assert d.status == "STANDBY"

    # Flag candidate anomalies
    app.anomalies[0].is_candidate = True
    app.anomalies[1].is_candidate = True

    # Fast-forward Master drone to end of waypoints
    app.current_wp_idx = len(app.lawnmower_waypoints) - 1
    app.master_drone.target_x, app.master_drone.target_y = app.lawnmower_waypoints[-1]
    app.master_drone.x, app.master_drone.y = app.lawnmower_waypoints[-1]

    # Step simulation: Master Drone lands at base and finishes Stage A
    app.update_simulation(dt=1.0)
    assert app.master_drone.status == "COMPLETED"
    assert app.mission_phase == 2  # Stage B initialized!

    # Verify multiple swarm drones launched concurrently!
    active_drones = [d for d in app.swarm_drones if d.status == "TRAVELLING"]
    assert len(active_drones) >= 2  # Multiple drones dispatched simultaneously!
    for d in active_drones:
        assert d.current_task_id is not None

    # Render canvas to verify flight path highlighting, trajectory badges, and stage banner
    app.render_canvas()
    dynamic_items = app.canvas.find_withtag("dynamic")
    assert len(dynamic_items) > 0




