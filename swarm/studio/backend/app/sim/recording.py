"""Simulation recording structures, telemetry frames, events, and summary data models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from app.planning.stage2 import DecisionRecord


class DroneFrame(BaseModel):
    id: int
    lat: float
    lon: float
    alt: float
    heading: float
    battery_pct: float
    state: str  # "STANDBY", "TAKEOFF", "CRUISE", "CAPTURE", "RTH", "LANDED", "HANDOVER"
    target_id: Optional[str] = None


class SimFrame(BaseModel):
    t: float
    drones: List[DroneFrame]


class SimEvent(BaseModel):
    t: float
    type: str  # "MISSION_START", "TAKEOFF", "CAPTURE", "HOTSPOT_REVEALED", "LOW_BATTERY_RTH", "HANDOVER", "STAGE2_START", "LANDED", "MISSION_COMPLETE"
    drone_id: Optional[int] = None
    target_id: Optional[str] = None
    detail: str


class SimCapture(BaseModel):
    id: str
    t: float
    drone_id: int
    stage: int  # 1 (Survey) or 2 (Detail)
    cell_id: Optional[str] = None
    lat: float
    lon: float
    alt: float
    heading: float
    footprint_polygon: List[Tuple[float, float]]
    gsd_mm_per_px: float
    temp_c: float
    rh_pct: float
    battery_pct: float
    image_url: str
    thumb_url: str
    label: str
    hotspot_type: Optional[str] = None
    hotspot_severity: float = 0.0


class SimSummary(BaseModel):
    total_time_s: float
    total_distance_m: float
    total_captures: int
    coverage_pct: float
    hotspots_total: int
    hotspots_revealed: int
    handovers_count: int
    energy_used_per_drone_Wh: Dict[int, float]
    drones_used: List[int]


class RunRecording(BaseModel):
    schema_version: int = 1
    config_snapshot: Dict[str, Any]
    seed: int
    frames: List[SimFrame]
    events: List[SimEvent]
    decisions: List[DecisionRecord]
    captures: List[SimCapture]
    summary: SimSummary
