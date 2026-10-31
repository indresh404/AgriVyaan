"""Scenario JSON load, save, and validation functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def validate_scenario_data(data: Dict[str, Any]) -> None:
    """Validate raw scenario data dictionary."""
    if not isinstance(data, dict):
        raise ValueError("Scenario data must be a JSON object")

    field_data = data.get("field")
    if not field_data:
        raise ValueError("Scenario missing 'field' definition")

    width = float(field_data.get("width_m", 0.0))
    height = float(field_data.get("height_m", 0.0))
    if width <= 0 or height <= 0:
        raise ValueError(f"Field width and height must be positive, got width={width}, height={height}")

    base = field_data.get("base_position", [0.0, 0.0])
    if not isinstance(base, (list, tuple)) or len(base) != 2:
        raise ValueError("Field 'base_position' must be a 2-element coordinate list [x, y]")
    bx, by = float(base[0]), float(base[1])
    if not (0.0 <= bx <= width and 0.0 <= by <= height):
        raise ValueError(f"Base position {base} outside field bounds [0, {width}]x[0, {height}]")

    tasks_data = data.get("tasks", [])
    if not isinstance(tasks_data, list):
        raise ValueError("'tasks' must be a list")

    seen_ids = set()
    for t in tasks_data:
        if not isinstance(t, dict):
            raise ValueError(f"Each task must be an object, got {type(t)}")
        tid = int(t.get("id", -1))
        if tid < 0:
            raise ValueError(f"Task ID must be non-negative, got {tid}")
        if tid in seen_ids:
            raise ValueError(f"Duplicate task ID found: {tid}")
        seen_ids.add(tid)

        pos = t.get("position")
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            raise ValueError(f"Task {tid} position must be a 2-element list [x, y]")
        x, y = float(pos[0]), float(pos[1])
        if not (0.0 <= x <= width and 0.0 <= y <= height):
            raise ValueError(f"Task {tid} position ({x}, {y}) is outside field bounds [0, {width}]x[0, {height}]")

        p = float(t.get("priority", 0.5))
        u = float(t.get("uncertainty", 0.5))
        g = float(t.get("expected_gain", 0.5))
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"Task {tid} priority {p} must be in [0, 1]")
        if not (0.0 <= u <= 1.0):
            raise ValueError(f"Task {tid} uncertainty {u} must be in [0, 1]")
        if not (0.0 <= g <= 1.0):
            raise ValueError(f"Task {tid} expected_gain {g} must be in [0, 1]")

        dur = float(t.get("duration_s", 10.0))
        if dur < 0:
            raise ValueError(f"Task {tid} duration {dur} must be non-negative")


def load_scenario_from_dict(data: Dict[str, Any]) -> Field:
    """Construct a Field with InspectionTasks from a dictionary."""
    validate_scenario_data(data)

    field_data = data["field"]
    width = float(field_data["width_m"])
    height = float(field_data["height_m"])
    base_pos = (float(field_data["base_position"][0]), float(field_data["base_position"][1]))

    field = Field(width_m=width, height_m=height, base_position=base_pos)

    tasks: List[InspectionTask] = []
    for t_data in data.get("tasks", []):
        task = InspectionTask(
            id=int(t_data["id"]),
            position=(float(t_data["position"][0]), float(t_data["position"][1])),
            priority=float(t_data.get("priority", 0.5)),
            uncertainty=float(t_data.get("uncertainty", 0.5)),
            expected_gain=float(t_data.get("expected_gain", 0.5)),
            duration_s=float(t_data.get("duration_s", 15.0)),
            inspection_energy_eu=float(t_data.get("inspection_energy_eu", 7.5)),
            status=TaskStatus(t_data.get("status", TaskStatus.PENDING.value)),
            assigned_drone_id=t_data.get("assigned_drone_id"),
            attempts=int(t_data.get("attempts", 0)),
            source_finding_id=t_data.get("source_finding_id"),
        )
        tasks.append(task)

    field.tasks = tasks
    return field


def load_scenario_file(path: str | Path) -> Field:
    """Load a scenario from a JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Scenario file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_scenario_from_dict(data)


def save_scenario_file(field: Field, path: str | Path) -> None:
    """Save a Field and its tasks to a JSON scenario file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "field": {
            "width_m": field.width_m,
            "height_m": field.height_m,
            "base_position": list(field.base_position),
        },
        "tasks": [
            {
                "id": t.id,
                "position": list(t.position),
                "priority": t.priority,
                "uncertainty": t.uncertainty,
                "expected_gain": t.expected_gain,
                "duration_s": t.duration_s,
                "inspection_energy_eu": t.inspection_energy_eu,
                "status": t.status.value,
                "attempts": t.attempts,
                "source_finding_id": t.source_finding_id,
            }
            for t in field.tasks
        ],
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def import_findings_scenario(
    findings_data: List[Dict[str, Any]],
    field_width_m: float = 100.0,
    field_height_m: float = 100.0,
    base_position: tuple[float, float] = (0.0, 0.0),
    default_duration_s: float = 20.0,
    inspect_rate_eu_per_s: float = 0.5,
) -> Field:
    """Import AgriVyaan Finding records into a simulated Field.

    Mapping rules (synthetic only):
        priority <- anomaly_score
        uncertainty <- 1 - evidence_strength
    """
    field = Field(width_m=field_width_m, height_m=field_height_m, base_position=base_position)
    tasks: List[InspectionTask] = []

    for idx, item in enumerate(findings_data):
        anomaly_score = float(item.get("anomaly_score", 0.5))
        evidence_strength = float(item.get("evidence_strength", 0.5))
        pos = (float(item.get("x", 0.0)), float(item.get("y", 0.0)))

        priority = max(0.0, min(1.0, anomaly_score))
        uncertainty = max(0.0, min(1.0, 1.0 - evidence_strength))
        expected_gain = float(item.get("expected_gain", round(priority * uncertainty, 3)))
        duration = float(item.get("duration_s", default_duration_s))

        tasks.append(
            InspectionTask(
                id=idx,
                position=pos,
                priority=priority,
                uncertainty=uncertainty,
                expected_gain=expected_gain,
                duration_s=duration,
                inspection_energy_eu=duration * inspect_rate_eu_per_s,
                status=TaskStatus.PENDING,
                source_finding_id=item.get("finding_id"),
            )
        )

    field.tasks = tasks
    return field
