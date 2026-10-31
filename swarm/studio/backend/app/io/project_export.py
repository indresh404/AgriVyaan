"""Export and import complete project packages with geometry, configuration, and state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlmodel import Session, select

from app.models import (
    Project,
    ProjectField,
    CropSettings,
    CameraSettings,
    DroneConfig,
    PlannedPath,
    HotspotEntity,
    utc_now,
)


def export_project_to_dict(session: Session, project_id: str) -> Dict[str, Any]:
    """Serialize full project configuration to dictionary."""
    proj = session.get(Project, project_id)
    if not proj:
        raise ValueError(f"Project {project_id} not found.")

    field = session.exec(select(ProjectField).where(ProjectField.project_id == project_id)).first()
    crop = session.exec(select(CropSettings).where(CropSettings.project_id == project_id)).first()
    camera = session.exec(select(CameraSettings).where(CameraSettings.project_id == project_id)).first()
    drones = session.exec(select(DroneConfig).where(DroneConfig.project_id == project_id)).all()
    paths = session.exec(select(PlannedPath).where(PlannedPath.project_id == project_id)).all()
    hotspots = session.exec(select(HotspotEntity).where(HotspotEntity.project_id == project_id)).all()

    return {
        "export_version": 1,
        "exported_at": utc_now().isoformat(),
        "project": proj.model_dump(),
        "field": field.model_dump() if field else None,
        "crop": crop.model_dump() if crop else None,
        "camera": camera.model_dump() if camera else None,
        "drones": [d.model_dump() for d in drones],
        "paths": [p.model_dump() for p in paths],
        "hotspots": [h.model_dump() for h in hotspots],
    }


def import_project_from_dict(session: Session, data: Dict[str, Any], new_id: Optional[str] = None) -> Project:
    """Restore or import full project from serialized dictionary."""
    p_data = data["project"]
    proj_id = new_id or p_data["id"]

    # Check if exists, update or create
    existing_proj = session.get(Project, proj_id)
    if existing_proj:
        existing_proj.name = p_data.get("name", existing_proj.name)
        existing_proj.base_lat = p_data.get("base_lat", existing_proj.base_lat)
        existing_proj.base_lon = p_data.get("base_lon", existing_proj.base_lon)
        existing_proj.updated_at = utc_now()
        session.add(existing_proj)
        proj = existing_proj
    else:
        proj = Project(
            id=proj_id,
            name=p_data.get("name", "Imported Farm Project"),
            base_lat=p_data.get("base_lat", 18.52043),
            base_lon=p_data.get("base_lon", 73.85671),
        )
        session.add(proj)
    session.commit()

    # Field
    if data.get("field"):
        f_data = data["field"]
        f = session.exec(select(ProjectField).where(ProjectField.project_id == proj_id)).first()
        if not f:
            f = ProjectField(project_id=proj_id)
        f.polygon_geojson = f_data.get("polygon_geojson", {})
        f.area_m2 = f_data.get("area_m2", 0.0)
        f.area_ha = f_data.get("area_ha", 0.0)
        f.area_acres = f_data.get("area_acres", 0.0)
        f.perimeter_m = f_data.get("perimeter_m", 0.0)
        f.bounds_json = f_data.get("bounds_json", {})
        session.add(f)

    # Crop
    if data.get("crop"):
        c_data = data["crop"]
        c = session.exec(select(CropSettings).where(CropSettings.project_id == proj_id)).first()
        if not c:
            c = CropSettings(project_id=proj_id)
        c.crop_type = c_data.get("crop_type", "potato")
        c.row_spacing_m = c_data.get("row_spacing_m", 0.75)
        c.row_angle_deg = c_data.get("row_angle_deg", 0.0)
        session.add(c)

    # Camera
    if data.get("camera"):
        cam_data = data["camera"]
        cam = session.exec(select(CameraSettings).where(CameraSettings.project_id == proj_id)).first()
        if not cam:
            cam = CameraSettings(project_id=proj_id)
        for k, v in cam_data.items():
            if k not in ("id", "project_id") and hasattr(cam, k):
                setattr(cam, k, v)
        session.add(cam)

    # Drones
    if "drones" in data:
        # Clear existing
        for old_d in session.exec(select(DroneConfig).where(DroneConfig.project_id == proj_id)).all():
            session.delete(old_d)
        for d_info in data["drones"]:
            d = DroneConfig(
                project_id=proj_id,
                drone_id=d_info.get("drone_id", 1),
                is_backup=d_info.get("is_backup", False),
                capacity_Wh=d_info.get("capacity_Wh", 74.0),
                power_hover_W=d_info.get("power_hover_W", 150.0),
                power_cruise_W=d_info.get("power_cruise_W", 160.0),
                power_climb_W=d_info.get("power_climb_W", 220.0),
                reserve_pct=d_info.get("reserve_pct", 25.0),
                initial_charge_pct=d_info.get("initial_charge_pct", 100.0),
                drain_multiplier=d_info.get("drain_multiplier", 1.0),
            )
            session.add(d)

    # Hotspots
    if "hotspots" in data:
        for old_h in session.exec(select(HotspotEntity).where(HotspotEntity.project_id == proj_id)).all():
            session.delete(old_h)
        for h_info in data["hotspots"]:
            h = HotspotEntity(
                project_id=proj_id,
                node_id=h_info["node_id"],
                lat=h_info["lat"],
                lon=h_info["lon"],
                type=h_info.get("type", "early_blight"),
                severity=h_info.get("severity", 0.8),
                note=h_info.get("note", ""),
                image_ref=h_info.get("image_ref"),
            )
            session.add(h)

    session.commit()
    session.refresh(proj)
    return proj
