"""FastAPI application main entrypoint and REST API routes."""

import json
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel

from app.db import create_db_and_tables, get_session
from app.models import (
    Project,
    ProjectField,
    CropSettings,
    CameraSettings,
    DroneConfig,
    PlannedPath,
    HotspotEntity,
    SimulationRun,
)
from app.geo.polygon import FieldGeometry
from app.geo.projection import LocalProjection
from app.camera.footprint import calculate_footprint
from app.camera.grid import generate_grid_plan, GridCell
from app.planning.path import sort_cells_boustrophedon, build_drone_path, Waypoint
from app.planning.partition import partition_cells_balanced
from app.planning.energy import DroneBatteryProfile, evaluate_flight_plan, PathEvaluationResult
from app.planning.validate import validate_flight_plan
from app.imagery.mosaic import build_field_mosaic
from app.imagery.uploads import save_user_orthophoto
from app.io.project_export import export_project_to_dict, import_project_from_dict
from app.io.geojson_kml import parse_geojson_polygon, parse_kml_polygon, polygon_to_geojson
from app.sim.engine import run_full_simulation


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="AgriVyaan Mission Studio API",
    description="Precision Agriculture Multi-UAV Swarm Mission Studio Backend",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Health & Disclaimer ---
@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "AgriVyaan Mission Studio",
        "simulation_disclaimer": "Simulation prototype. Detections are marked areas, not AI. Battery/time are editable models.",
    }


@app.get("/api/crops/potato")
def get_potato_profile():
    profile_path = Path(__file__).resolve().parent / "crop_profiles" / "potato.json"
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Potato profile not found.")


# --- Project CRUD ---
class CreateProjectRequest(BaseModel):
    name: str = "My Potato Farm"
    base_lat: float = 18.52043
    base_lon: float = 73.85671


@app.get("/api/projects")
def list_projects(session: Session = Depends(get_session)):
    projects = session.exec(select(Project)).all()
    return projects


@app.post("/api/projects")
def create_project(req: CreateProjectRequest, session: Session = Depends(get_session)):
    proj_id = f"proj-{uuid.uuid4().hex[:8]}"
    proj = Project(
        id=proj_id,
        name=req.name,
        base_lat=req.base_lat,
        base_lon=req.base_lon,
    )
    session.add(proj)

    # Initialize default settings
    field = ProjectField(project_id=proj_id)
    crop = CropSettings(project_id=proj_id)
    camera = CameraSettings(project_id=proj_id)

    # Default 2 active drones + 1 backup drone
    d1 = DroneConfig(project_id=proj_id, drone_id=1, is_backup=False, initial_charge_pct=100.0)
    d2 = DroneConfig(project_id=proj_id, drone_id=2, is_backup=False, initial_charge_pct=100.0)
    d3 = DroneConfig(project_id=proj_id, drone_id=3, is_backup=True, initial_charge_pct=100.0)

    session.add(field)
    session.add(crop)
    session.add(camera)
    session.add(d1)
    session.add(d2)
    session.add(d3)

    session.commit()
    session.refresh(proj)
    return proj


@app.get("/api/projects/{project_id}")
def get_project_details(project_id: str, session: Session = Depends(get_session)):
    proj = session.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found.")

    field = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    crop = session.exec(select(CropSettings).where(CropSettings.project_id == project_id)).first()
    camera = session.exec(select(CameraSettings).where(CameraSettings.project_id == project_id)).first()
    drones = session.exec(select(DroneConfig).where(DroneConfig.project_id == project_id)).all()
    paths = session.exec(select(PlannedPath).where(PlannedPath.project_id == project_id)).all()
    hotspots = session.exec(select(HotspotEntity).where(HotspotEntity.project_id == project_id)).all()

    return {
        "project": proj,
        "field": field,
        "crop": crop,
        "camera": camera,
        "drones": drones,
        "paths": paths,
        "hotspots": hotspots,
    }


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, session: Session = Depends(get_session)):
    proj = session.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found.")

    for entity_cls in (ProjectField, CropSettings, CameraSettings, DroneConfig, PlannedPath, HotspotEntity, SimulationRun):
        for item in session.exec(select(entity_cls).where(entity_cls.project_id == project_id)).all():
            session.delete(item)
    session.delete(proj)
    session.commit()
    return {"status": "deleted", "project_id": project_id}


# --- Settings Updates ---
class UpdateFieldRequest(BaseModel):
    coordinates: List[Tuple[float, float]]  # [(lat, lon), ...]
    base_lat: Optional[float] = None
    base_lon: Optional[float] = None


@app.put("/api/projects/{project_id}/field")
def update_field(project_id: str, req: UpdateFieldRequest, session: Session = Depends(get_session)):
    proj = session.get(Project, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found.")

    if len(req.coordinates) < 3:
        raise HTTPException(status_code=400, detail="Polygon must have at least 3 vertices.")

    geom = FieldGeometry(req.coordinates)
    field = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    if not field:
        field = ProjectField(project_id=project_id)

    field.polygon_geojson = polygon_to_geojson(req.coordinates)
    field.area_m2 = round(geom.area_m2, 2)
    field.area_ha = round(geom.area_ha, 3)
    field.area_acres = round(geom.area_acres, 3)
    field.perimeter_m = round(geom.perimeter_m, 2)
    field.bounds_json = geom.bounds_latlon
    session.add(field)

    if req.base_lat is not None and req.base_lon is not None:
        proj.base_lat = req.base_lat
        proj.base_lon = req.base_lon
        session.add(proj)

    session.commit()
    session.refresh(field)

    # Generate illustrative crop rows
    crop = session.exec(select(CropSettings).where(CropSettings.project_id == project_id)).first()
    spacing = crop.row_spacing_m if crop else 0.75
    angle = crop.row_angle_deg if crop else 0.0
    crop_rows = geom.generate_crop_rows(spacing_m=spacing, angle_deg=angle)

    return {
        "field": field,
        "crop_rows": crop_rows,
        "longest_edge_angle_deg": round(geom.longest_edge_angle_deg(), 1),
    }


class UpdateCropRequest(BaseModel):
    crop_type: str = "potato"
    row_spacing_m: float = 0.75
    row_angle_deg: float = 0.0


@app.put("/api/projects/{project_id}/crop")
def update_crop(project_id: str, req: UpdateCropRequest, session: Session = Depends(get_session)):
    crop = session.exec(select(CropSettings).where(CropSettings.project_id == project_id)).first()
    if not crop:
        crop = CropSettings(project_id=project_id)
    crop.crop_type = req.crop_type
    crop.row_spacing_m = max(0.2, req.row_spacing_m)
    crop.row_angle_deg = req.row_angle_deg
    session.add(crop)
    session.commit()
    session.refresh(crop)
    return crop


class UpdateCameraRequest(BaseModel):
    preset_name: str = "Pi Camera HQ (6mm Lens)"
    sensor_w_mm: float = 6.287
    sensor_h_mm: float = 4.712
    focal_length_mm: float = 6.0
    image_w_px: int = 4056
    image_h_px: int = 3040
    altitude_survey_m: float = 20.0
    altitude_detail_m: float = 8.0
    speed_survey_m_s: float = 6.0
    speed_detail_m_s: float = 3.5
    edge_margin: float = 0.20
    grid_angle_deg: float = 0.0


@app.put("/api/projects/{project_id}/camera")
def update_camera(project_id: str, req: UpdateCameraRequest, session: Session = Depends(get_session)):
    cam = session.exec(select(CameraSettings).where(CameraSettings.project_id == project_id)).first()
    if not cam:
        cam = CameraSettings(project_id=project_id)
    for k, v in req.model_dump().items():
        if hasattr(cam, k):
            setattr(cam, k, v)
    session.add(cam)
    session.commit()
    session.refresh(cam)
    return cam


class DroneConfigItem(BaseModel):
    drone_id: int
    is_backup: bool = False
    capacity_Wh: float = 74.0
    power_hover_W: float = 150.0
    power_cruise_W: float = 160.0
    power_climb_W: float = 220.0
    reserve_pct: float = 25.0
    initial_charge_pct: float = 100.0
    drain_multiplier: float = 1.0


@app.put("/api/projects/{project_id}/drones")
def update_drones(project_id: str, req: List[DroneConfigItem], session: Session = Depends(get_session)):
    for old_d in session.exec(select(DroneConfig).where(DroneConfig.project_id == project_id)).all():
        session.delete(old_d)
    new_drones = []
    for item in req:
        d = DroneConfig(
            project_id=project_id,
            drone_id=item.drone_id,
            is_backup=item.is_backup,
            capacity_Wh=item.capacity_Wh,
            power_hover_W=item.power_hover_W,
            power_cruise_W=item.power_cruise_W,
            power_climb_W=item.power_climb_W,
            reserve_pct=item.reserve_pct,
            initial_charge_pct=item.initial_charge_pct,
            drain_multiplier=item.drain_multiplier,
        )
        session.add(d)
        new_drones.append(d)
    session.commit()
    return new_drones


class HotspotItem(BaseModel):
    node_id: str
    lat: float
    lon: float
    type: str = "early_blight"
    severity: float = 0.8
    note: str = ""
    image_ref: Optional[str] = None


@app.put("/api/projects/{project_id}/hotspots")
def update_hotspots(project_id: str, req: List[HotspotItem], session: Session = Depends(get_session)):
    for old_h in session.exec(select(HotspotEntity).where(HotspotEntity.project_id == project_id)).all():
        session.delete(old_h)
    new_hotspots = []
    for item in req:
        h = HotspotEntity(
            project_id=project_id,
            node_id=item.node_id,
            lat=item.lat,
            lon=item.lon,
            type=item.type,
            severity=item.severity,
            note=item.note,
            image_ref=item.image_ref,
        )
        session.add(h)
        new_hotspots.append(h)
    session.commit()
    return new_hotspots


class PathUpdateItem(BaseModel):
    drone_id: int
    stage: int = 1
    mode: str = "auto"
    waypoints: List[Dict[str, Any]]


@app.put("/api/projects/{project_id}/paths")
def update_paths(project_id: str, req: List[PathUpdateItem], session: Session = Depends(get_session)):
    for old_p in session.exec(select(PlannedPath).where(PlannedPath.project_id == project_id)).all():
        session.delete(old_p)
    new_paths = []
    for item in req:
        p = PlannedPath(
            project_id=project_id,
            drone_id=item.drone_id,
            stage=item.stage,
            mode=item.mode,
            waypoints_json=item.waypoints,
        )
        session.add(p)
        new_paths.append(p)
    session.commit()
    return new_paths


# --- Plan Preview & Validation ---
@app.post("/api/projects/{project_id}/plan/preview")
def preview_flight_plan(project_id: str, session: Session = Depends(get_session)):
    proj = session.get(Project, project_id)
    field_record = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    camera = session.exec(select(CameraSettings).where(CameraSettings.project_id == project_id)).first()
    drones = session.exec(select(DroneConfig).where(DroneConfig.project_id == project_id)).all()

    if not proj or not field_record or not field_record.polygon_geojson:
        raise HTTPException(status_code=400, detail="Field polygon has not been set.")

    coords = field_record.polygon_geojson.get("geometry", {}).get("coordinates", [[]])[0]
    latlon_coords = [(pt[1], pt[0]) for pt in coords]
    if len(latlon_coords) < 3:
        raise HTTPException(status_code=400, detail="Invalid field polygon.")

    field = FieldGeometry(latlon_coords)
    alt = camera.altitude_survey_m if camera else 20.0
    margin = camera.edge_margin if camera else 0.20
    angle = camera.grid_angle_deg if camera else 0.0

    # 1. Grid Plan
    grid_res = generate_grid_plan(field, altitude_m=alt, margin=margin, grid_angle_deg=angle)
    serpentine_cells = sort_cells_boustrophedon(grid_res.cells)

    # 2. Partition among active drones (exclude backup)
    active_drones = [d for d in drones if not d.is_backup] or [
        DroneConfig(drone_id=1, is_backup=False)
    ]
    base_x, base_y = field.proj.forward(proj.base_lon, proj.base_lat)

    chunks = partition_cells_balanced(
        serpentine_cells,
        num_active_drones=len(active_drones),
        base_x_m=base_x,
        base_y_m=base_y,
        speed_m_s=camera.speed_survey_m_s if camera else 6.0,
    )

    drone_paths: Dict[int, List[Waypoint]] = {}
    drone_evaluations = []

    for i, d in enumerate(active_drones):
        chunk = chunks[i] if i < len(chunks) else []
        wps = build_drone_path(chunk, proj.base_lat, proj.base_lon, altitude_m=alt, proj=field.proj)
        drone_paths[d.drone_id] = wps

        prof = DroneBatteryProfile(
            capacity_Wh=d.capacity_Wh,
            power_hover_W=d.power_hover_W,
            power_cruise_W=d.power_cruise_W,
            power_climb_W=d.power_climb_W,
            reserve_pct=d.reserve_pct,
            initial_charge_pct=d.initial_charge_pct,
            drain_multiplier=d.drain_multiplier,
            speed_m_s=camera.speed_survey_m_s if camera else 6.0,
        )
        eval_res = evaluate_flight_plan(d.drone_id, wps, prof, altitude_m=alt)
        drone_evaluations.append(eval_res)

    fp_info = calculate_footprint(
        alt,
        sensor_w_mm=camera.sensor_w_mm if camera else 6.287,
        sensor_h_mm=camera.sensor_h_mm if camera else 4.712,
        focal_length_mm=camera.focal_length_mm if camera else 6.0,
        image_w_px=camera.image_w_px if camera else 4056,
        image_h_px=camera.image_h_px if camera else 3040,
    )

    return {
        "footprint": fp_info,
        "grid": grid_res,
        "active_drones_count": len(active_drones),
        "backup_drones_count": len(drones) - len(active_drones),
        "drone_evaluations": drone_evaluations,
        "drone_paths": {d_id: [w.model_dump() for w in wps] for d_id, wps in drone_paths.items()},
    }


@app.post("/api/projects/{project_id}/plan/validate")
def validate_plan_endpoint(project_id: str, session: Session = Depends(get_session)):
    preview = preview_flight_plan(project_id, session)

    field_record = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    coords = field_record.polygon_geojson.get("geometry", {}).get("coordinates", [[]])[0]
    latlon_coords = [(pt[1], pt[0]) for pt in coords]
    field = FieldGeometry(latlon_coords)

    # Use models from preview
    grid_cells = preview["grid"].cells
    evals = preview["drone_evaluations"]
    paths = {
        int(k): [Waypoint(**w) for w in wps] for k, wps in preview["drone_paths"].items()
    }

    alt = preview["footprint"].altitude_m
    val_result = validate_flight_plan(field, alt, grid_cells, evals, paths)
    return val_result


# --- Imagery ---
@app.post("/api/projects/{project_id}/imagery/prepare")
def prepare_imagery(project_id: str, session: Session = Depends(get_session)):
    field_record = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    if not field_record or not field_record.bounds_json:
        raise HTTPException(status_code=400, detail="Field bounds have not been set.")

    b = field_record.bounds_json
    mosaic_res = build_field_mosaic(
        project_id,
        south=b["south"],
        north=b["north"],
        west=b["west"],
        east=b["east"],
        zoom=18,
    )
    return mosaic_res


@app.get("/api/projects/{project_id}/mosaic")
def get_project_mosaic(project_id: str, thumb: bool = False):
    mosaic_file = "mosaic_thumb.jpg" if thumb else "mosaic.jpg"
    mosaic_path = Path(__file__).resolve().parent.parent.parent / "data" / "projects" / project_id / mosaic_file
    if mosaic_path.exists():
        return FileResponse(str(mosaic_path), media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Mosaic image not found. Call prepare first.")


# --- Project Export & Import ---
@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str, session: Session = Depends(get_session)):
    try:
        data = export_project_to_dict(session, project_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/projects/import")
def import_project(data: Dict[str, Any], session: Session = Depends(get_session)):
    try:
        proj = import_project_from_dict(session, data)
        return {"status": "imported", "project_id": proj.id, "name": proj.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- GeoJSON & KML Import ---
class GeoImportRequest(BaseModel):
    content: str


@app.post("/api/geo/import-geojson")
def import_geojson(req: GeoImportRequest):
    try:
        coords = parse_geojson_polygon(req.content)
        return {"coordinates": coords, "count": len(coords)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GeoJSON parse error: {e}")


@app.post("/api/geo/import-kml")
def import_kml(req: GeoImportRequest):
    try:
        coords = parse_kml_polygon(req.content)
        return {"coordinates": coords, "count": len(coords)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"KML parse error: {e}")


# --- Simulation Execution & Replay ---
class SimulateRequest(BaseModel):
    seed: int = 42


@app.post("/api/projects/{project_id}/simulate")
def run_simulation_endpoint(
    project_id: str,
    req: SimulateRequest = SimulateRequest(),
    session: Session = Depends(get_session),
):
    proj = session.get(Project, project_id)
    field_record = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    camera = session.exec(select(CameraSettings).where(CameraSettings.project_id == project_id)).first()
    drones = session.exec(select(DroneConfig).where(DroneConfig.project_id == project_id)).all()
    hotspots = session.exec(select(HotspotEntity).where(HotspotEntity.project_id == project_id)).all()

    if not proj or not field_record or not field_record.polygon_geojson:
        raise HTTPException(status_code=400, detail="Field polygon has not been set.")

    coords = field_record.polygon_geojson.get("geometry", {}).get("coordinates", [[]])[0]
    latlon_coords = [(pt[1], pt[0]) for pt in coords]
    field = FieldGeometry(latlon_coords)

    # Check for prepared mosaic
    proj_dir = Path(__file__).resolve().parent.parent.parent / "data" / "projects" / project_id
    mosaic_file = proj_dir / "mosaic.jpg"
    mosaic_path = str(mosaic_file) if mosaic_file.exists() else None
    mosaic_bounds = field_record.bounds_json

    # Run full simulation engine
    recording = run_full_simulation(
        project=proj,
        field=field,
        camera=camera or CameraSettings(project_id=project_id),
        drones_config=drones or [DroneConfig(project_id=project_id, drone_id=1, is_backup=False)],
        hotspots_entities=hotspots,
        seed=req.seed,
        mosaic_path=mosaic_path,
        mosaic_bounds=mosaic_bounds,
    )

    # Save recording to disk
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    runs_dir = proj_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    rec_path = runs_dir / f"{run_id}.json"

    with open(rec_path, "w", encoding="utf-8") as f:
        f.write(recording.model_dump_json(indent=2))

    # Persist run record
    sim_run = SimulationRun(
        run_id=run_id,
        project_id=project_id,
        recording_file_path=str(rec_path),
        summary_json=recording.summary.model_dump(),
    )
    session.add(sim_run)
    session.commit()

    return {
        "run_id": run_id,
        "summary": recording.summary,
        "recording_url": f"/api/runs/{run_id}/recording",
    }


@app.get("/api/runs/{run_id}/recording")
def get_recording(run_id: str, session: Session = Depends(get_session)):
    sim_run = session.exec(select(SimulationRun).where(SimulationRun.run_id == run_id)).first()
    if not sim_run or not Path(sim_run.recording_file_path).exists():
        raise HTTPException(status_code=404, detail="Simulation recording not found.")

    with open(sim_run.recording_file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/captures/{capture_id}/image")
def get_capture_image(capture_id: str):
    captures_dir = Path(__file__).resolve().parent.parent.parent / "data" / "captures"
    img_path = captures_dir / f"{capture_id}.jpg"
    if img_path.exists():
        return FileResponse(str(img_path), media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Capture image not found.")


@app.get("/api/captures/{capture_id}/thumb")
def get_capture_thumb(capture_id: str):
    captures_dir = Path(__file__).resolve().parent.parent.parent / "data" / "captures"
    thumb_path = captures_dir / f"{capture_id}_thumb.jpg"
    if thumb_path.exists():
        return FileResponse(str(thumb_path), media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Capture thumbnail not found.")
