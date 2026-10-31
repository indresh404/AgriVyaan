"""Backend math, geometry, camera footprint, path planning, and energy tests for Phase 1."""

import math
import pytest
from app.geo.projection import LocalProjection, get_utm_epsg
from app.geo.polygon import FieldGeometry
from app.camera.footprint import calculate_footprint
from app.camera.grid import generate_grid_plan
from app.planning.path import sort_cells_boustrophedon, build_drone_path
from app.planning.partition import partition_cells_balanced
from app.planning.energy import (
    DroneBatteryProfile,
    evaluate_flight_plan,
)
from app.planning.validate import validate_flight_plan
from app.planning.stage2 import HotspotMark, cluster_hotspots


def test_camera_footprint_and_gsd_self_check():
    """Verify Section 6.2 camera footprint and exact GSD self-check from prompt.

    Self-check test: Pi Camera HQ, 6 mm lens, 14.5 m gives GSD of about 3.75 mm/px.
    At 20 m, Fw is about 20.96 m and Fh about 15.7 m.
    """
    # 1. At 14.5 m altitude
    fp_14 = calculate_footprint(
        altitude_m=14.5,
        sensor_w_mm=6.287,
        sensor_h_mm=4.712,
        focal_length_mm=6.0,
        image_w_px=4056,
        image_h_px=3040,
    )
    # 6.287 * 14500 / (6.0 * 4056) = 3.7459... mm/px -> rounds to 3.75
    assert round(fp_14.gsd_mm_per_px, 2) == 3.75

    # 2. At 20 m altitude
    fp_20 = calculate_footprint(
        altitude_m=20.0,
        sensor_w_mm=6.287,
        sensor_h_mm=4.712,
        focal_length_mm=6.0,
        image_w_px=4056,
        image_h_px=3040,
    )
    # Fw = 20 * 6.287 / 6 = 20.95666... -> ~20.96 m
    # Fh = 20 * 4.712 / 6 = 15.70666... -> ~15.7 m
    assert round(fp_20.footprint_w_m, 2) == 20.96
    assert round(fp_20.footprint_h_m, 1) == 15.7


def test_polygon_geometry_and_utm_projection():
    """Verify polygon area, perimeter, and UTM forward/inverse transformation."""
    # 100m x 100m square in Pune (18.52043°N, 73.85671°E)
    ref_lat, ref_lon = 18.52043, 73.85671
    proj = LocalProjection(ref_lat, ref_lon)
    assert proj.epsg == 32643  # UTM Zone 43N

    x0, y0 = proj.forward(ref_lon, ref_lat)
    coords_m = [
        (x0, y0),
        (x0, y0 + 100.0),
        (x0 + 100.0, y0 + 100.0),
        (x0 + 100.0, y0),
    ]
    latlon_coords = []
    for xm, ym in coords_m:
        lon, lat = proj.inverse(xm, ym)
        latlon_coords.append((lat, lon))

    field = FieldGeometry(latlon_coords)
    # 100m x 100m = 10,000 m² = 1.00 Ha
    assert pytest.approx(field.area_m2, rel=1e-3) == 10000.0
    assert pytest.approx(field.area_ha, rel=1e-3) == 1.00
    assert pytest.approx(field.perimeter_m, rel=1e-3) == 400.0

    # Crop rows generation
    rows = field.generate_crop_rows(spacing_m=2.0, angle_deg=0.0)
    assert len(rows) > 0


def test_grid_plan_generation_and_coverage():
    """Verify grid generation clipped to field polygon and coverage threshold."""
    ref_lat, ref_lon = 18.52043, 73.85671
    proj = LocalProjection(ref_lat, ref_lon)
    x0, y0 = proj.forward(ref_lon, ref_lat)

    latlon_coords = [
        proj.inverse(x0, y0)[::-1],
        proj.inverse(x0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0)[::-1],
    ]
    field = FieldGeometry(latlon_coords)

    plan = generate_grid_plan(field, altitude_m=20.0, margin=0.2, min_fraction=0.05)
    assert plan.kept_cells > 0
    assert plan.coverage_pct >= 90.0
    assert plan.cell_side_m > 5.0


def test_boustrophedon_path_partition_and_length():
    """Verify boustrophedon sequence, multi-drone partitioning, and path length."""
    ref_lat, ref_lon = 18.52043, 73.85671
    proj = LocalProjection(ref_lat, ref_lon)
    x0, y0 = proj.forward(ref_lon, ref_lat)

    latlon_coords = [
        proj.inverse(x0, y0)[::-1],
        proj.inverse(x0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0)[::-1],
    ]
    field = FieldGeometry(latlon_coords)
    plan = generate_grid_plan(field, altitude_m=20.0, margin=0.2)

    serpentine = sort_cells_boustrophedon(plan.cells)
    assert len(serpentine) == len(plan.cells)

    # Partition for 2 active drones
    chunks = partition_cells_balanced(
        serpentine, num_active_drones=2, base_x_m=x0, base_y_m=y0, speed_m_s=6.0
    )
    assert len(chunks) == 2
    assert len(chunks[0]) + len(chunks[1]) == len(plan.cells)

    # Build path for drone 1
    d1_waypoints = build_drone_path(chunks[0], ref_lat, ref_lon, altitude_m=20.0, proj=proj)
    assert len(d1_waypoints) >= len(chunks[0]) + 3
    assert d1_waypoints[0].action == "TAKEOFF"
    assert d1_waypoints[-1].action == "LAND"

    # Evaluate flight plan
    profile = DroneBatteryProfile(capacity_Wh=74.0, initial_charge_pct=100.0)
    eval_res = evaluate_flight_plan(1, d1_waypoints, profile, altitude_m=20.0)

    # Path length equals sum of leg distances
    expected_dist = sum(
        math.hypot(
            d1_waypoints[i + 1].x_m - d1_waypoints[i].x_m,
            d1_waypoints[i + 1].y_m - d1_waypoints[i].y_m,
        )
        for i in range(len(d1_waypoints) - 1)
    )
    assert pytest.approx(eval_res.path_length_m, abs=0.1) == expected_dist
    assert eval_res.energy_used_Wh > 0.0
    assert eval_res.is_battery_sufficient is True


def test_battery_depletion_and_plan_validation():
    """Verify low battery triggers validation error and uncovered cells are detected."""
    ref_lat, ref_lon = 18.52043, 73.85671
    proj = LocalProjection(ref_lat, ref_lon)
    x0, y0 = proj.forward(ref_lon, ref_lat)

    latlon_coords = [
        proj.inverse(x0, y0)[::-1],
        proj.inverse(x0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0 + 100.0)[::-1],
        proj.inverse(x0 + 100.0, y0)[::-1],
    ]
    field = FieldGeometry(latlon_coords)
    plan = generate_grid_plan(field, altitude_m=20.0)
    serpentine = sort_cells_boustrophedon(plan.cells)

    chunks = partition_cells_balanced(
        serpentine, num_active_drones=2, base_x_m=x0, base_y_m=y0
    )
    d1_wps = build_drone_path(chunks[0], ref_lat, ref_lon, altitude_m=20.0, proj=proj)
    d2_wps = build_drone_path(chunks[1], ref_lat, ref_lon, altitude_m=20.0, proj=proj)

    # 1. Normal sufficient profile
    prof_ok = DroneBatteryProfile(capacity_Wh=74.0, initial_charge_pct=100.0)
    eval1 = evaluate_flight_plan(1, d1_wps, prof_ok, altitude_m=20.0)
    eval2 = evaluate_flight_plan(2, d2_wps, prof_ok, altitude_m=20.0)

    val_res = validate_flight_plan(
        field,
        20.0,
        plan.cells,
        [eval1, eval2],
        {1: d1_wps, 2: d2_wps},
    )
    assert val_res.is_valid is True

    # 2. Artificially depleted battery on Drone 1 (15% initial charge)
    prof_depleted = DroneBatteryProfile(capacity_Wh=74.0, initial_charge_pct=15.0, reserve_pct=25.0)
    eval1_depleted = evaluate_flight_plan(1, d1_wps, prof_depleted, altitude_m=20.0)
    assert eval1_depleted.is_battery_sufficient is False

    val_res_fail = validate_flight_plan(
        field,
        20.0,
        plan.cells,
        [eval1_depleted, eval2],
        {1: d1_wps, 2: d2_wps},
    )
    assert val_res_fail.is_valid is False
    assert any("Battery" in m or "Drone 1" in m for m in val_res_fail.messages)


def test_stage2_hotspot_clustering():
    """Verify Stage-2 distance threshold clustering and priority ranking."""
    ref_lat, ref_lon = 18.52043, 73.85671
    proj = LocalProjection(ref_lat, ref_lon)

    # 3 hotspots: two close together (<25m), one far away (>60m)
    h1_lat, h1_lon = ref_lat + 0.0001, ref_lon + 0.0001
    h2_lat, h2_lon = ref_lat + 0.00015, ref_lon + 0.00012
    h3_lat, h3_lon = ref_lat + 0.0008, ref_lon + 0.0008

    hotspots = [
        HotspotMark(id="H-1", lat=h1_lat, lon=h1_lon, type="late_blight", severity=0.9),
        HotspotMark(id="H-2", lat=h2_lat, lon=h2_lon, type="late_blight", severity=0.7),
        HotspotMark(id="H-3", lat=h3_lat, lon=h3_lon, type="aphid", severity=0.5),
    ]

    clusters = cluster_hotspots(hotspots, proj, distance_threshold_m=25.0, stage2_alt_m=8.0)
    assert len(clusters) == 2  # H-1 & H-2 merged, H-3 separate
    assert clusters[0].priority_score >= clusters[1].priority_score
    assert len(clusters[0].subgrid_waypoints) >= 2
