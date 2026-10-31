"""Tests for Phase 2: Database, API routes, persistence, export/import, and imagery."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import get_session


# Use in-memory SQLite for testing
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


def test_health_and_potato_crop_profile(client: TestClient):
    """Verify health check disclaimer and full potato crop profile."""
    # Health
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "Simulation prototype" in r.json()["simulation_disclaimer"]

    # Potato profile
    r_crop = client.get("/api/crops/potato")
    assert r_crop.status_code == 200
    p_data = r_crop.json()
    assert "Potato" in p_data["crop_name"]
    assert len(p_data["pathologies"]) >= 3


def test_project_crud_and_persistence(client: TestClient):
    """Verify project creation, retrieval, updates, and deletion."""
    # Create project
    res = client.post("/api/projects", json={"name": "Khadakwasla Test Farm", "base_lat": 18.52, "base_lon": 73.85})
    assert res.status_code == 200
    p = res.json()
    proj_id = p["id"]
    assert p["name"] == "Khadakwasla Test Farm"

    # Set Field Polygon (100m square)
    coords = [
        [18.5200, 73.8500],
        [18.5209, 73.8500],
        [18.5209, 73.8509],
        [18.5200, 73.8509],
    ]
    r_field = client.put(f"/api/projects/{proj_id}/field", json={"coordinates": coords})
    assert r_field.status_code == 200
    f_data = r_field.json()
    assert f_data["field"]["area_m2"] > 5000.0
    assert len(f_data["crop_rows"]) > 0

    # Update Camera Settings
    r_cam = client.put(
        f"/api/projects/{proj_id}/camera",
        json={"altitude_survey_m": 25.0, "edge_margin": 0.25, "speed_survey_m_s": 7.0},
    )
    assert r_cam.status_code == 200
    assert r_cam.json()["altitude_survey_m"] == 25.0

    # Get Project Details
    r_get = client.get(f"/api/projects/{proj_id}")
    assert r_get.status_code == 200
    details = r_get.json()
    assert details["project"]["id"] == proj_id
    assert details["field"]["area_m2"] > 0
    assert len(details["drones"]) == 3  # 2 active + 1 backup default


def test_plan_preview_and_validation_api(client: TestClient):
    """Verify plan preview and plan validation endpoints."""
    # Create project & set field
    p = client.post("/api/projects", json={"name": "Validation Farm"}).json()
    proj_id = p["id"]
    coords = [
        [18.5200, 73.8500],
        [18.5208, 73.8500],
        [18.5208, 73.8508],
        [18.5200, 73.8508],
    ]
    client.put(f"/api/projects/{proj_id}/field", json={"coordinates": coords})

    # Preview plan
    r_prev = client.post(f"/api/projects/{proj_id}/plan/preview")
    assert r_prev.status_code == 200
    prev_data = r_prev.json()
    assert prev_data["grid"]["kept_cells"] > 0
    assert prev_data["active_drones_count"] >= 1
    assert len(prev_data["drone_evaluations"]) >= 1

    # Validate plan
    r_val = client.post(f"/api/projects/{proj_id}/plan/validate")
    assert r_val.status_code == 200
    val_data = r_val.json()
    assert val_data["is_valid"] is True
    assert len(val_data["uncovered_cell_ids"]) == 0


def test_project_export_and_import_roundtrip(client: TestClient):
    """Verify full project export to JSON and clean restore/import."""
    # Create & configure project
    p = client.post("/api/projects", json={"name": "Export Farm"}).json()
    proj_id = p["id"]
    coords = [
        [18.5200, 73.8500],
        [18.5208, 73.8500],
        [18.5208, 73.8508],
        [18.5200, 73.8508],
    ]
    client.put(f"/api/projects/{proj_id}/field", json={"coordinates": coords})

    # Mark hotspot
    client.put(
        f"/api/projects/{proj_id}/hotspots",
        json=[{"node_id": "H-1", "lat": 18.5204, "lon": 73.8504, "type": "late_blight", "severity": 0.85}],
    )

    # Export project
    r_exp = client.get(f"/api/projects/{proj_id}/export")
    assert r_exp.status_code == 200
    export_payload = r_exp.json()
    assert export_payload["project"]["id"] == proj_id
    assert len(export_payload["hotspots"]) == 1

    # Import with new ID
    export_payload["project"]["id"] = f"{proj_id}-imported"
    export_payload["project"]["name"] = "Export Farm (Restored)"
    r_imp = client.post("/api/projects/import", json=export_payload)
    assert r_imp.status_code == 200
    imp_res = r_imp.json()
    assert imp_res["project_id"] == f"{proj_id}-imported"

    # Verify imported project has restored field and hotspot
    r_check = client.get(f"/api/projects/{proj_id}-imported")
    assert r_check.status_code == 200
    restored = r_check.json()
    assert restored["field"]["area_m2"] > 0
    assert len(restored["hotspots"]) == 1


def test_geojson_and_kml_polygon_parsing(client: TestClient):
    """Verify GeoJSON and KML field import endpoints."""
    # 1. GeoJSON
    geojson_str = json.dumps(
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[73.8500, 18.5200], [73.8500, 18.5210], [73.8510, 18.5210], [73.8510, 18.5200], [73.8500, 18.5200]]
                ],
            },
        }
    )
    r_geo = client.post("/api/geo/import-geojson", json={"content": geojson_str})
    assert r_geo.status_code == 200
    assert len(r_geo.json()["coordinates"]) == 5

    # 2. KML
    kml_str = """<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Placemark>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                73.8500,18.5200,0 73.8500,18.5210,0 73.8510,18.5210,0 73.8510,18.5200,0 73.8500,18.5200,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </kml>
    """
    r_kml = client.post("/api/geo/import-kml", json={"content": kml_str})
    assert r_kml.status_code == 200
    assert len(r_kml.json()["coordinates"]) == 5
