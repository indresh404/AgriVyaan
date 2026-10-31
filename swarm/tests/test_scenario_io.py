"""Tests for scenario JSON loading, validation, and serialization."""

import pytest
from pathlib import Path
from agrivyaan_swarm.scenario_io import (
    load_scenario_file,
    save_scenario_file,
    validate_scenario_data,
    import_findings_scenario,
)


def test_load_fixed_10_scenario():
    """Verify loading fixed_10.json scenario."""
    fixed_path = Path("data/scenarios/fixed_10.json")
    field = load_scenario_file(fixed_path)

    assert field.width_m == 100.0
    assert field.height_m == 100.0
    assert len(field.tasks) == 10
    assert field.tasks[0].id == 0
    assert field.tasks[0].position == (15.0, 20.0)


def test_save_and_reload_scenario(tmp_path):
    """Verify round-trip save and load of scenario."""
    fixed_path = Path("data/scenarios/fixed_10.json")
    field = load_scenario_file(fixed_path)

    tmp_file = tmp_path / "scenario_copy.json"
    save_scenario_file(field, tmp_file)

    reloaded = load_scenario_file(tmp_file)
    assert reloaded.width_m == field.width_m
    assert reloaded.height_m == field.height_m
    assert len(reloaded.tasks) == len(field.tasks)
    for orig, rel in zip(field.tasks, reloaded.tasks):
        assert orig.id == rel.id
        assert orig.position == rel.position
        assert orig.priority == rel.priority


def test_scenario_validation_errors():
    """Ensure invalid scenario data triggers descriptive ValueErrors."""
    # Invalid dimensions
    with pytest.raises(ValueError, match="Field width and height must be positive"):
        validate_scenario_data({"field": {"width_m": -10, "height_m": 50}})

    # Task out of bounds
    with pytest.raises(ValueError, match="outside field bounds"):
        validate_scenario_data({
            "field": {"width_m": 100, "height_m": 100, "base_position": [0, 0]},
            "tasks": [{"id": 1, "position": [150, 50], "priority": 0.5}],
        })

    # Duplicate task IDs
    with pytest.raises(ValueError, match="Duplicate task ID"):
        validate_scenario_data({
            "field": {"width_m": 100, "height_m": 100, "base_position": [0, 0]},
            "tasks": [
                {"id": 1, "position": [10, 10], "priority": 0.5},
                {"id": 1, "position": [20, 20], "priority": 0.5},
            ],
        })


def test_import_findings_mapping():
    """Verify AgriVyaan findings mapping: priority <- anomaly_score, uncertainty <- 1 - evidence_strength."""
    findings = [
        {"finding_id": "F-101", "x": 10.0, "y": 20.0, "anomaly_score": 0.85, "evidence_strength": 0.3},
    ]
    field = import_findings_scenario(findings)
    assert len(field.tasks) == 1
    t = field.tasks[0]
    assert t.source_finding_id == "F-101"
    assert t.priority == 0.85
    assert abs(t.uncertainty - 0.70) < 1e-5
