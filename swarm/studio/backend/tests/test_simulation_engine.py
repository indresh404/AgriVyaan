"""Tests for Phase 3: Full Simulation Engine, Two-Stage logic, Handover, and Determinism."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import get_session
from app.models import Project, ProjectField, CameraSettings, DroneConfig, HotspotEntity
from app.geo.polygon import FieldGeometry
from app.sim.engine import run_full_simulation


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_simulation_engine_end_to_end_and_determinism():
    """Verify full two-stage simulation runs end-to-end and is 100% deterministic with identical seed."""
    ref_lat, ref_lon = 18.52043, 73.85671
    project = Project(id="test-sim-proj", name="Deterministic Sim Farm", base_lat=ref_lat, base_lon=ref_lon)

    # 100m x 100m field
    latlon_coords = [
        (ref_lat, ref_lon),
        (ref_lat + 0.0009, ref_lon),
        (ref_lat + 0.0009, ref_lon + 0.0009),
        (ref_lat, ref_lon + 0.0009),
    ]
    field = FieldGeometry(latlon_coords)

    camera = CameraSettings(
        altitude_survey_m=20.0,
        altitude_detail_m=8.0,
        speed_survey_m_s=6.0,
        speed_detail_m_s=3.5,
    )

    drones = [
        DroneConfig(drone_id=1, is_backup=False, capacity_Wh=74.0, initial_charge_pct=100.0),
        DroneConfig(drone_id=2, is_backup=False, capacity_Wh=74.0, initial_charge_pct=100.0),
        DroneConfig(drone_id=3, is_backup=True, capacity_Wh=74.0, initial_charge_pct=100.0),
    ]

    hotspots = [
        HotspotEntity(node_id="H-1", lat=ref_lat + 0.0004, lon=ref_lon + 0.0004, type="late_blight", severity=0.9),
        HotspotEntity(node_id="H-2", lat=ref_lat + 0.0006, lon=ref_lon + 0.0006, type="early_blight", severity=0.7),
    ]

    # Run 1
    rec1 = run_full_simulation(
        project, field, camera, drones, hotspots, seed=123
    )

    # Run 2 with same seed
    rec2 = run_full_simulation(
        project, field, camera, drones, hotspots, seed=123
    )

    # 1. Determinism verification
    assert len(rec1.frames) == len(rec2.frames)
    assert len(rec1.captures) == len(rec2.captures)
    assert len(rec1.events) == len(rec2.events)
    assert rec1.summary.total_time_s == rec2.summary.total_time_s
    assert rec1.summary.coverage_pct == rec2.summary.coverage_pct

    # 2. Content verification
    assert rec1.summary.total_captures > 0
    assert rec1.summary.coverage_pct >= 80.0
    assert any(ev.type == "MISSION_START" for ev in rec1.events)
    assert any(ev.type == "CAPTURE" for ev in rec1.events)
    assert any(ev.type == "MISSION_COMPLETE" for ev in rec1.events)


def test_low_battery_handover_to_backup_drone():
    """Verify depleted battery on Drone 1 triggers RTH and handover to backup Drone 3."""
    ref_lat, ref_lon = 18.52043, 73.85671
    project = Project(id="test-handover-proj", name="Handover Farm", base_lat=ref_lat, base_lon=ref_lon)

    latlon_coords = [
        (ref_lat, ref_lon),
        (ref_lat + 0.0009, ref_lon),
        (ref_lat + 0.0009, ref_lon + 0.0009),
        (ref_lat, ref_lon + 0.0009),
    ]
    field = FieldGeometry(latlon_coords)
    camera = CameraSettings(altitude_survey_m=20.0, speed_survey_m_s=6.0)

    # Drone 1 forced with low initial battery (28% initial charge with 25% reserve)
    drones = [
        DroneConfig(drone_id=1, is_backup=False, capacity_Wh=74.0, initial_charge_pct=28.0, reserve_pct=25.0),
        DroneConfig(drone_id=2, is_backup=False, capacity_Wh=74.0, initial_charge_pct=100.0, reserve_pct=25.0),
        DroneConfig(drone_id=3, is_backup=True, capacity_Wh=74.0, initial_charge_pct=100.0, reserve_pct=25.0),
    ]

    recording = run_full_simulation(project, field, camera, drones, [], seed=42)

    # Must have triggered LOW_BATTERY_RTH and HANDOVER
    rth_events = [ev for ev in recording.events if ev.type == "LOW_BATTERY_RTH"]
    handover_events = [ev for ev in recording.events if ev.type == "HANDOVER"]

    assert len(rth_events) >= 1
    assert len(handover_events) >= 1
    assert any(ev.drone_id == 3 for ev in handover_events)
    assert len(recording.decisions) >= 1
    assert recording.summary.handovers_count >= 1


def test_simulation_api_endpoint(client: TestClient):
    """Verify POST /api/projects/{id}/simulate and GET /api/runs/{id}/recording."""
    # Create project & set field
    p = client.post("/api/projects", json={"name": "API Sim Farm"}).json()
    proj_id = p["id"]
    coords = [
        [18.5200, 73.8500],
        [18.5208, 73.8500],
        [18.5208, 73.8508],
        [18.5200, 73.8508],
    ]
    client.put(f"/api/projects/{proj_id}/field", json={"coordinates": coords})

    # Add hotspot
    client.put(
        f"/api/projects/{proj_id}/hotspots",
        json=[{"node_id": "H-1", "lat": 18.5204, "lon": 73.8504, "type": "late_blight", "severity": 0.85}],
    )

    # Run simulation
    r_sim = client.post(f"/api/projects/{proj_id}/simulate", json={"seed": 42})
    assert r_sim.status_code == 200
    sim_data = r_sim.json()
    run_id = sim_data["run_id"]
    assert sim_data["summary"]["total_captures"] > 0

    # Fetch recording
    r_rec = client.get(f"/api/runs/{run_id}/recording")
    assert r_rec.status_code == 200
    rec_json = r_rec.json()
    assert rec_json["schema_version"] == 1
    assert len(rec_json["frames"]) > 10
    assert len(rec_json["captures"]) > 0

    # Test capture image retrieval
    first_cap_id = rec_json["captures"][0]["id"]
    r_cap_img = client.get(f"/api/captures/{first_cap_id}/image")
    assert r_cap_img.status_code == 200
    assert r_cap_img.headers["content-type"] == "image/jpeg"
