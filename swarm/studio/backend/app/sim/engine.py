"""Deterministic full multi-drone simulation engine with two-stage survey & handover."""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Tuple
from shapely.geometry import Point, box, Polygon
from shapely.affinity import rotate

from app.models import Project, ProjectField, CameraSettings, DroneConfig, HotspotEntity
from app.geo.polygon import FieldGeometry
from app.camera.footprint import calculate_footprint
from app.camera.grid import generate_grid_plan, GridCell
from app.planning.path import sort_cells_boustrophedon, build_drone_path, Waypoint
from app.planning.partition import partition_cells_balanced
from app.planning.energy import DroneBatteryProfile, heading_between
from app.planning.stage2 import HotspotMark, cluster_hotspots, DecisionRecord, CandidateEvaluation
from app.environment.synthetic import SyntheticEnvironment
from app.imagery.crops import extract_capture_crop
from app.sim.battery import DroneBatterySim
from app.sim.handover import evaluate_handover_candidates
from app.sim.recording import (
    DroneFrame,
    SimFrame,
    SimEvent,
    SimCapture,
    SimSummary,
    RunRecording,
)


def run_full_simulation(
    project: Project,
    field: FieldGeometry,
    camera: CameraSettings,
    drones_config: List[DroneConfig],
    hotspots_entities: List[HotspotEntity],
    seed: int = 42,
    mosaic_path: Optional[str] = None,
    mosaic_bounds: Optional[Dict[str, float]] = None,
) -> RunRecording:
    """Run full deterministic multi-UAV precision flight simulation at 10 Hz."""
    proj = field.proj
    base_x, base_y = proj.forward(project.base_lon, project.base_lat)

    # Footprint properties
    alt_s1 = camera.altitude_survey_m
    alt_s2 = camera.altitude_detail_m
    speed_s1 = camera.speed_survey_m_s
    speed_s2 = camera.speed_detail_m_s

    fp_s1 = calculate_footprint(
        alt_s1,
        sensor_w_mm=camera.sensor_w_mm,
        sensor_h_mm=camera.sensor_h_mm,
        focal_length_mm=camera.focal_length_mm,
        image_w_px=camera.image_w_px,
        image_h_px=camera.image_h_px,
    )

    # 1. Generate Stage 1 Grid & Paths
    grid_plan = generate_grid_plan(
        field,
        altitude_m=alt_s1,
        margin=camera.edge_margin,
        grid_angle_deg=camera.grid_angle_deg,
    )
    serpentine = sort_cells_boustrophedon(grid_plan.cells)

    active_d_configs = [d for d in drones_config if not d.is_backup] or [
        DroneConfig(drone_id=1, is_backup=False)
    ]
    backup_d_configs = [d for d in drones_config if d.is_backup]

    chunks = partition_cells_balanced(
        serpentine,
        num_active_drones=len(active_d_configs),
        base_x_m=base_x,
        base_y_m=base_y,
        speed_m_s=speed_s1,
    )

    # 2. Initialize Drone Simulation States
    drone_states: Dict[int, Dict[str, Any]] = {}
    for i, d in enumerate(active_d_configs):
        chunk = chunks[i] if i < len(chunks) else []
        wps = build_drone_path(chunk, project.base_lat, project.base_lon, altitude_m=alt_s1, proj=proj)

        prof = DroneBatteryProfile(
            capacity_Wh=d.capacity_Wh,
            power_hover_W=d.power_hover_W,
            power_cruise_W=d.power_cruise_W,
            power_climb_W=d.power_climb_W,
            reserve_pct=d.reserve_pct,
            initial_charge_pct=d.initial_charge_pct,
            drain_multiplier=d.drain_multiplier,
            speed_m_s=speed_s1,
        )
        drone_states[d.drone_id] = {
            "drone_id": d.drone_id,
            "is_backup": False,
            "profile": prof,
            "battery_sim": DroneBatterySim(prof),
            "waypoints": wps,
            "wp_idx": 0,
            "x_m": base_x,
            "y_m": base_y,
            "lat": project.base_lat,
            "lon": project.base_lon,
            "alt_m": 0.0,
            "heading": 0.0,
            "state": "STANDBY",
            "dwell_remaining_s": 0.0,
            "total_dist_m": 0.0,
            "active_stage": 1,
        }

    for b in backup_d_configs:
        prof_b = DroneBatteryProfile(
            capacity_Wh=b.capacity_Wh,
            power_hover_W=b.power_hover_W,
            power_cruise_W=b.power_cruise_W,
            power_climb_W=b.power_climb_W,
            reserve_pct=b.reserve_pct,
            initial_charge_pct=b.initial_charge_pct,
            drain_multiplier=b.drain_multiplier,
            speed_m_s=speed_s1,
        )
        drone_states[b.drone_id] = {
            "drone_id": b.drone_id,
            "is_backup": True,
            "profile": prof_b,
            "battery_sim": DroneBatterySim(prof_b),
            "waypoints": [],
            "wp_idx": 0,
            "x_m": base_x,
            "y_m": base_y,
            "lat": project.base_lat,
            "lon": project.base_lon,
            "alt_m": 0.0,
            "heading": 0.0,
            "state": "STANDBY",
            "dwell_remaining_s": 0.0,
            "total_dist_m": 0.0,
            "active_stage": 1,
        }

    # 3. Environment & Hotspots Setup
    env = SyntheticEnvironment(base_temp_c=24.5, base_rh_pct=65.0, seed=seed)
    hotspots = [
        HotspotMark(
            id=h.node_id,
            lat=h.lat,
            lon=h.lon,
            type=h.type,
            severity=h.severity,
            note=h.note,
        )
        for h in hotspots_entities
    ]

    # Pre-project hotspots to metric coordinates for fast collision check
    hotspot_metrics = []
    for h in hotspots:
        hx, hy = proj.forward(h.lon, h.lat)
        hotspot_metrics.append((h, hx, hy))

    # Recording containers
    frames: List[SimFrame] = []
    events: List[SimEvent] = []
    decisions: List[DecisionRecord] = []
    captures: List[SimCapture] = []
    handovers_count = 0

    events.append(
        SimEvent(
            t=0.0,
            type="MISSION_START",
            detail=f"Mission launched with {len(active_d_configs)} active drones and {len(backup_d_configs)} backup standby.",
        )
    )

    # Start active drones
    for d_id in [d.drone_id for d in active_d_configs]:
        d = drone_states[d_id]
        if d["waypoints"]:
            d["state"] = "TAKEOFF"
            events.append(
                SimEvent(
                    t=0.0,
                    type="TAKEOFF",
                    drone_id=d_id,
                    detail=f"Drone {d_id} airborne from Base. Commencing Stage 1 survey.",
                )
            )

    # Simulation loop parameters
    dt = 0.1  # 10 Hz
    sim_time = 0.0
    max_sim_time = 3600.0  # 1 hour safety limit

    stage1_active = True
    stage2_prepared = False

    while sim_time < max_sim_time:
        all_drones_idle = True
        frame_drone_list: List[DroneFrame] = []

        # Update each drone
        for d_id, d in drone_states.items():
            state = d["state"]
            battery = d["battery_sim"]

            # Battery energy update
            battery.consume(state, dt)

            # State machine handling
            if state in ("STANDBY", "LANDED"):
                pass  # Stationary at base

            elif state == "TAKEOFF":
                all_drones_idle = False
                target_alt = alt_s1 if d["active_stage"] == 1 else alt_s2
                d["alt_m"] = min(target_alt, d["alt_m"] + d["profile"].climb_rate_m_s * dt)
                if d["alt_m"] >= target_alt - 0.1:
                    d["alt_m"] = target_alt
                    d["state"] = "CRUISE"
                    if d["wp_idx"] == 0 and len(d["waypoints"]) > 1:
                        d["wp_idx"] = 1  # Head to first destination waypoint

            elif state == "CAPTURE":
                all_drones_idle = False
                d["dwell_remaining_s"] -= dt
                if d["dwell_remaining_s"] <= 0.0:
                    d["state"] = "CRUISE"
                    d["wp_idx"] += 1

            elif state in ("CRUISE", "RTH"):
                all_drones_idle = False
                wps = d["waypoints"]

                if d["wp_idx"] >= len(wps):
                    # Arrived at end of path
                    d["state"] = "LANDED"
                    d["alt_m"] = 0.0
                    events.append(
                        SimEvent(
                            t=round(sim_time, 1),
                            type="LANDED",
                            drone_id=d_id,
                            detail=f"Drone {d_id} landed at Base Station.",
                        )
                    )
                else:
                    curr_wp = wps[d["wp_idx"]]
                    target_x, target_y = curr_wp.x_m, curr_wp.y_m
                    dx = target_x - d["x_m"]
                    dy = target_y - d["y_m"]
                    dist = math.hypot(dx, dy)
                    speed = speed_s1 if d["active_stage"] == 1 else speed_s2
                    step = speed * dt

                    if dist > 1e-4:
                        d["heading"] = heading_between((d["x_m"], d["y_m"]), (target_x, target_y))

                    if step >= dist:
                        # Reached waypoint
                        d["x_m"] = target_x
                        d["y_m"] = target_y
                        d["total_dist_m"] += dist
                        lon, lat = proj.inverse(d["x_m"], d["y_m"])
                        d["lon"] = round(lon, 7)
                        d["lat"] = round(lat, 7)

                        if curr_wp.action == "CAPTURE":
                            d["state"] = "CAPTURE"
                            d["dwell_remaining_s"] = d["profile"].dwell_time_s

                            # 1. Trigger capture & footprint check
                            cap_id = f"CAP-{len(captures)+1:03d}"
                            curr_alt = d["alt_m"]
                            fp_w = curr_alt * (camera.sensor_w_mm / camera.focal_length_mm)
                            fp_h = curr_alt * (camera.sensor_h_mm / camera.focal_length_mm)
                            gsd = (camera.sensor_w_mm * (curr_alt * 1000.0)) / (
                                camera.focal_length_mm * camera.image_w_px
                            )

                            # Footprint polygon coordinates
                            fp_box = box(
                                d["x_m"] - fp_w / 2.0,
                                d["y_m"] - fp_h / 2.0,
                                d["x_m"] + fp_w / 2.0,
                                d["y_m"] + fp_h / 2.0,
                            )
                            fp_rot = rotate(fp_box, d["heading"], origin=(d["x_m"], d["y_m"]))
                            fp_latlon = [
                                (round(proj.inverse(pt[0], pt[1])[1], 7), round(proj.inverse(pt[0], pt[1])[0], 7))
                                for pt in list(fp_rot.exterior.coords)
                            ]

                            # Check proximity to hotspots
                            nearest_blight_dist = 999.0
                            matched_hotspot: Optional[HotspotMark] = None
                            for h_obj, hx, hy in hotspot_metrics:
                                h_dist = math.hypot(hx - d["x_m"], hy - d["y_m"])
                                if "blight" in h_obj.type and h_dist < nearest_blight_dist:
                                    nearest_blight_dist = h_dist
                                # Check if footprint intersects hotspot
                                if fp_rot.contains(Point(hx, hy)):
                                    matched_hotspot = h_obj
                                    if not h_obj.revealed:
                                        h_obj.revealed = True
                                        h_obj.revealed_at_s = sim_time
                                        events.append(
                                            SimEvent(
                                                t=round(sim_time, 1),
                                                type="HOTSPOT_REVEALED",
                                                drone_id=d_id,
                                                target_id=h_obj.id,
                                                detail=f"Drone {d_id} revealed {h_obj.type.replace('_', ' ').title()} ({h_obj.id}) with severity {h_obj.severity*100:.0f}%.",
                                            )
                                        )

                            # Sample environment
                            t_c, rh_p = env.sample(d["lat"], d["lon"], sim_time, nearest_blight_dist)

                            # Extract crop image
                            img_path, thumb_path = extract_capture_crop(
                                mosaic_path=mosaic_path or "",
                                mosaic_bounds=mosaic_bounds or {},
                                center_lat=d["lat"],
                                center_lon=d["lon"],
                                footprint_w_m=fp_w,
                                footprint_h_m=fp_h,
                                hotspot_type=matched_hotspot.type if matched_hotspot else None,
                                hotspot_severity=matched_hotspot.severity if matched_hotspot else 0.0,
                                capture_id=cap_id,
                            )

                            cap = SimCapture(
                                id=cap_id,
                                t=round(sim_time, 1),
                                drone_id=d_id,
                                stage=d["active_stage"],
                                cell_id=curr_wp.cell_id,
                                lat=d["lat"],
                                lon=d["lon"],
                                alt=round(d["alt_m"], 1),
                                heading=round(d["heading"], 1),
                                footprint_polygon=fp_latlon,
                                gsd_mm_per_px=round(gsd, 2),
                                temp_c=t_c,
                                rh_pct=rh_p,
                                battery_pct=battery.battery_pct,
                                image_url=f"/api/captures/{cap_id}/image",
                                thumb_url=f"/api/captures/{cap_id}/thumb",
                                label=matched_hotspot.type if matched_hotspot else "Healthy Crop Canopy",
                                hotspot_type=matched_hotspot.type if matched_hotspot else None,
                                hotspot_severity=matched_hotspot.severity if matched_hotspot else 0.0,
                            )
                            captures.append(cap)
                            events.append(
                                SimEvent(
                                    t=round(sim_time, 1),
                                    type="CAPTURE",
                                    drone_id=d_id,
                                    target_id=curr_wp.cell_id,
                                    detail=f"Drone {d_id} captured {curr_wp.cell_id or 'point'} at alt {d['alt_m']:.1f}m (GSD: {gsd:.2f}mm/px, {t_c}°C, {rh_p}% RH).",
                                )
                            )

                        elif curr_wp.action in ("RTH", "LAND"):
                            d["state"] = "LANDED"
                            d["alt_m"] = 0.0
                            events.append(
                                SimEvent(
                                    t=round(sim_time, 1),
                                    type="LANDED",
                                    drone_id=d_id,
                                    detail=f"Drone {d_id} landed at Base Station.",
                                )
                            )
                        else:
                            d["wp_idx"] += 1

                    else:
                        d["x_m"] += (dx / dist) * step
                        d["y_m"] += (dy / dist) * step
                        d["total_dist_m"] += step
                        lon, lat = proj.inverse(d["x_m"], d["y_m"])
                        d["lon"] = round(lon, 7)
                        d["lat"] = round(lat, 7)

                    # Reserve Battery Feasibility Check during flight
                    if state == "CRUISE" and not battery.can_continue(d["x_m"], d["y_m"], base_x, base_y, d["alt_m"]):
                        # Low Battery trigger!
                        d["state"] = "RTH"
                        events.append(
                            SimEvent(
                                t=round(sim_time, 1),
                                type="LOW_BATTERY_RTH",
                                drone_id=d_id,
                                detail=f"Drone {d_id} battery reached return threshold ({battery.battery_pct}%). Initiating RTH and handover.",
                            )
                        )

                        # Extract unfinished waypoints
                        unfinished = [wp for wp in d["waypoints"][d["wp_idx"] :] if wp.action == "CAPTURE"]
                        # Set drone path to return home
                        d["waypoints"] = [
                            Waypoint(
                                index=0,
                                lat=project.base_lat,
                                lon=project.base_lon,
                                x_m=base_x,
                                y_m=base_y,
                                altitude_m=alt_s1,
                                action="RTH",
                            )
                        ]
                        d["wp_idx"] = 0

                        # Perform handover evaluation
                        if unfinished:
                            handovers_count += 1
                            active_pool = [d_info for i_id, d_info in drone_states.items() if not d_info["is_backup"]]
                            backup_pool = [d_info for i_id, d_info in drone_states.items() if d_info["is_backup"]]

                            chosen_d_id, reason, dec = evaluate_handover_candidates(
                                unfinished,
                                active_pool,
                                backup_pool,
                                base_x,
                                base_y,
                                sim_time,
                                low_drone_id=d_id,
                            )
                            decisions.append(dec)

                            if chosen_d_id and chosen_d_id in drone_states:
                                target_drone = drone_states[chosen_d_id]
                                if target_drone["is_backup"]:
                                    # Launch backup drone to unfinished cells
                                    takeover_path = build_drone_path(
                                        [GridCell(**{"cell_id": wp.cell_id, "row": 0, "col": 0, "center_lat": wp.lat, "center_lon": wp.lon, "center_x_m": wp.x_m, "center_y_m": wp.y_m, "polygon_latlon": [], "fraction_inside": 1.0}) for wp in unfinished],
                                        project.base_lat,
                                        project.base_lon,
                                        altitude_m=alt_s1,
                                        proj=proj,
                                    )
                                    target_drone["waypoints"] = takeover_path
                                    target_drone["wp_idx"] = 0
                                    target_drone["state"] = "TAKEOFF"
                                    events.append(
                                        SimEvent(
                                            t=round(sim_time, 1),
                                            type="HANDOVER",
                                            drone_id=chosen_d_id,
                                            detail=f"Backup Drone {chosen_d_id} activated! Took over {len(unfinished)} cells from Drone {d_id}.",
                                        )
                                    )
                                else:
                                    # Append unfinished waypoints to target active drone
                                    target_drone["waypoints"] = (
                                        target_drone["waypoints"][: target_drone["wp_idx"] + 1]
                                        + unfinished
                                        + target_drone["waypoints"][target_drone["wp_idx"] + 1 :]
                                    )
                                    events.append(
                                        SimEvent(
                                            t=round(sim_time, 1),
                                            type="HANDOVER",
                                            drone_id=chosen_d_id,
                                            detail=f"Active Drone {chosen_d_id} reassigned to complete {len(unfinished)} cells from Drone {d_id}.",
                                        )
                                    )

            frame_drone_list.append(
                DroneFrame(
                    id=d_id,
                    lat=d["lat"],
                    lon=d["lon"],
                    alt=round(d["alt_m"], 1),
                    heading=round(d["heading"], 1),
                    battery_pct=battery.battery_pct,
                    state=d["state"],
                    target_id=d["waypoints"][d["wp_idx"]].cell_id if d["wp_idx"] < len(d["waypoints"]) else None,
                )
            )

        # Record simulation frame
        frames.append(SimFrame(t=round(sim_time, 1), drones=frame_drone_list))

        # Check Stage 1 completion and Stage 2 transition
        if stage1_active:
            all_stage1_done = all(
                d["state"] in ("LANDED", "STANDBY") for d in drone_states.values() if not d["is_backup"]
            )
            # If active drones landed or all captures done
            if all_stage1_done:
                stage1_active = False
                revealed_hotspots = [h for h in hotspots if h.revealed]
                if revealed_hotspots and not stage2_prepared:
                    stage2_prepared = True
                    events.append(
                        SimEvent(
                            t=round(sim_time, 1),
                            type="STAGE2_START",
                            detail=f"Stage 1 survey completed. {len(revealed_hotspots)} hotspots revealed. Clustering for Stage 2 micro-inspection.",
                        )
                    )
                    clusters = cluster_hotspots(revealed_hotspots, proj, distance_threshold_m=25.0, stage2_alt_m=alt_s2)

                    # Assign clusters to operational drones
                    avail_drones = [d for d in drone_states.values() if d["battery_sim"].battery_pct >= 40.0]
                    if avail_drones and clusters:
                        for idx, cluster in enumerate(clusters):
                            assigned_drone = avail_drones[idx % len(avail_drones)]
                            cluster.assigned_drone_id = assigned_drone["drone_id"]

                            # Build Stage 2 path
                            s2_path = [
                                Waypoint(
                                    index=0,
                                    lat=project.base_lat,
                                    lon=project.base_lon,
                                    x_m=base_x,
                                    y_m=base_y,
                                    altitude_m=alt_s2,
                                    action="TAKEOFF",
                                )
                            ] + cluster.subgrid_waypoints + [
                                Waypoint(
                                    index=len(cluster.subgrid_waypoints) + 1,
                                    lat=project.base_lat,
                                    lon=project.base_lon,
                                    x_m=base_x,
                                    y_m=base_y,
                                    altitude_m=alt_s2,
                                    action="RTH",
                                ),
                                Waypoint(
                                    index=len(cluster.subgrid_waypoints) + 2,
                                    lat=project.base_lat,
                                    lon=project.base_lon,
                                    x_m=base_x,
                                    y_m=base_y,
                                    altitude_m=0.0,
                                    action="LAND",
                                ),
                            ]

                            assigned_drone["waypoints"] = s2_path
                            assigned_drone["wp_idx"] = 0
                            assigned_drone["active_stage"] = 2
                            assigned_drone["state"] = "TAKEOFF"

                            # Log decision record
                            decisions.append(
                                DecisionRecord(
                                    t=round(sim_time, 1),
                                    drone_id=assigned_drone["drone_id"],
                                    rule="STAGE2_CLUSTER_GREEDY_ASSIGNMENT",
                                    candidates=[
                                        CandidateEvaluation(
                                            cluster_id=cluster.cluster_id,
                                            distance_m=round(math.hypot(cluster.center_x_m - base_x, cluster.center_y_m - base_y), 1),
                                            energy_Wh=0.0,
                                            priority=cluster.priority_score,
                                            score=cluster.priority_score,
                                            feasible=True,
                                        )
                                    ],
                                    chosen_cluster_id=cluster.cluster_id,
                                    reason=f"Drone {assigned_drone['drone_id']} assigned {cluster.cluster_id} (Priority: {cluster.priority_score:.1f}, {len(cluster.hotspot_ids)} hotspots).",
                                )
                            )

        # Exit condition: all drones are LANDED or STANDBY after Stage 1 & Stage 2
        all_landed = all(d["state"] in ("LANDED", "STANDBY") for d in drone_states.values())
        if all_landed and sim_time > 5.0 and (not stage1_active or not revealed_hotspots if 'revealed_hotspots' in locals() else True):
            break

        sim_time += dt

    events.append(
        SimEvent(
            t=round(sim_time, 1),
            type="MISSION_COMPLETE",
            detail=f"Mission accomplished at {sim_time:.1f}s. All assigned zones inspected and all drones landed.",
        )
    )

    # 4. Compute Summary Statistics
    total_dist = sum(d["total_dist_m"] for d in drone_states.values())
    energy_per_drone = {d_id: round(d["battery_sim"].total_energy_used_Wh, 2) for d_id, d in drone_states.items()}
    drones_used = [d_id for d_id, d in drone_states.items() if d["total_dist_m"] > 10.0]

    captured_cells = {c.cell_id for c in captures if c.cell_id}
    all_grid_cells = {cell.cell_id for cell in grid_plan.cells}
    cov_pct = round((len(captured_cells) / max(1, len(all_grid_cells))) * 100.0, 1)

    summary = SimSummary(
        total_time_s=round(sim_time, 1),
        total_distance_m=round(total_dist, 1),
        total_captures=len(captures),
        coverage_pct=cov_pct,
        hotspots_total=len(hotspots_entities),
        hotspots_revealed=sum(1 for h in hotspots if h.revealed),
        handovers_count=handovers_count,
        energy_used_per_drone_Wh=energy_per_drone,
        drones_used=drones_used,
    )

    config_snapshot = {
        "project": project.model_dump(),
        "camera": camera.model_dump(),
        "drones": [d.model_dump() for d in drones_config],
        "grid_cells_count": len(grid_plan.cells),
    }

    return RunRecording(
        schema_version=1,
        config_snapshot=config_snapshot,
        seed=seed,
        frames=frames,
        events=events,
        decisions=decisions,
        captures=captures,
        summary=summary,
    )
