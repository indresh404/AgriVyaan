"""SQLModel database models and schema definitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlmodel import Field, SQLModel, Column, JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    schema_version: int = Field(default=1)
    base_lat: float = Field(default=18.52043)
    base_lon: float = Field(default=73.85671)


class ProjectField(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    polygon_geojson: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    area_m2: float = Field(default=0.0)
    area_ha: float = Field(default=0.0)
    area_acres: float = Field(default=0.0)
    perimeter_m: float = Field(default=0.0)
    bounds_json: Dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON))


class CropSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    crop_type: str = Field(default="potato")
    row_spacing_m: float = Field(default=0.75)
    row_angle_deg: float = Field(default=0.0)


class CameraSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    preset_name: str = Field(default="Pi Camera HQ (6mm Lens)")
    sensor_w_mm: float = Field(default=6.287)
    sensor_h_mm: float = Field(default=4.712)
    focal_length_mm: float = Field(default=6.0)
    image_w_px: int = Field(default=4056)
    image_h_px: int = Field(default=3040)
    altitude_survey_m: float = Field(default=20.0)
    altitude_detail_m: float = Field(default=8.0)
    speed_survey_m_s: float = Field(default=6.0)
    speed_detail_m_s: float = Field(default=3.5)
    edge_margin: float = Field(default=0.20)
    grid_angle_deg: float = Field(default=0.0)


class DroneConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    drone_id: int = Field(default=1)
    is_backup: bool = Field(default=False)
    capacity_Wh: float = Field(default=74.0)
    power_hover_W: float = Field(default=150.0)
    power_cruise_W: float = Field(default=160.0)
    power_climb_W: float = Field(default=220.0)
    reserve_pct: float = Field(default=25.0)
    initial_charge_pct: float = Field(default=100.0)
    drain_multiplier: float = Field(default=1.0)


class PlannedPath(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    drone_id: int = Field(default=1)
    stage: int = Field(default=1)
    mode: str = Field(default="auto")  # "auto" or "manual"
    waypoints_json: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class HotspotEntity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    node_id: str = Field(index=True)
    lat: float
    lon: float
    type: str = Field(default="early_blight")
    severity: float = Field(default=0.8)
    note: str = Field(default="")
    image_ref: Optional[str] = Field(default=None)


class SimulationRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, unique=True)
    project_id: str = Field(index=True, foreign_key="project.id")
    created_at: datetime = Field(default_factory=utc_now)
    recording_file_path: str = Field(default="")
    summary_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
