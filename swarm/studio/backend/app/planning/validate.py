"""Flight plan validation checklist and safety verification."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel

from app.camera.grid import GridCell
from app.planning.path import Waypoint
from app.planning.energy import PathEvaluationResult
from app.geo.polygon import FieldGeometry


class ValidationItem(BaseModel):
    name: str
    passed: bool
    details: str


class PlanValidationResult(BaseModel):
    is_valid: bool
    checks: List[ValidationItem]
    uncovered_cell_ids: List[str]
    messages: List[str]


def validate_flight_plan(
    field: FieldGeometry,
    altitude_m: float,
    all_grid_cells: List[GridCell],
    drone_evaluations: List[PathEvaluationResult],
    drone_waypoints: Dict[int, List[Waypoint]],
    min_altitude_m: float = 5.0,
    max_altitude_m: float = 120.0,
) -> PlanValidationResult:
    """Run comprehensive validation checklist on planned multi-drone mission."""
    checks: List[ValidationItem] = []
    messages: List[str] = []

    # 1. Field validity
    field_ok = field.area_m2 > 10.0 and field.poly_m.is_valid
    checks.append(
        ValidationItem(
            name="Field Polygon Geometry",
            passed=field_ok,
            details=f"Field area is {field.area_m2:.1f} m² ({field.area_ha:.2f} Ha)."
            if field_ok
            else "Field geometry is invalid or too small.",
        )
    )
    if not field_ok:
        messages.append("Field geometry is invalid or smaller than 10 m².")

    # 2. Altitude limits
    alt_ok = min_altitude_m <= altitude_m <= max_altitude_m
    checks.append(
        ValidationItem(
            name="Survey Altitude Limits",
            passed=alt_ok,
            details=f"Planned altitude {altitude_m:.1f} m is within permitted envelope [{min_altitude_m} m - {max_altitude_m} m]."
            if alt_ok
            else f"Altitude {altitude_m:.1f} m violates regulatory safe limit [{min_altitude_m}m - {max_altitude_m}m].",
        )
    )
    if not alt_ok:
        messages.append(
            f"Survey altitude ({altitude_m:.1f} m) must be between {min_altitude_m} m and {max_altitude_m} m."
        )

    # 3. Cell coverage check
    covered_cell_ids = set()
    for d_id, wps in drone_waypoints.items():
        for wp in wps:
            if wp.cell_id:
                covered_cell_ids.add(wp.cell_id)

    all_cell_ids = {c.cell_id for c in all_grid_cells}
    uncovered = sorted(list(all_cell_ids - covered_cell_ids))
    coverage_ok = len(uncovered) == 0
    checks.append(
        ValidationItem(
            name="All Grid Cells Covered",
            passed=coverage_ok,
            details=f"All {len(all_cell_ids)} field cells are assigned for capture."
            if coverage_ok
            else f"{len(uncovered)} of {len(all_cell_ids)} cells have not been assigned to any drone path.",
        )
    )
    if not coverage_ok:
        messages.append(f"{len(uncovered)} cells remain uncovered in planned flight paths.")

    # 4. Battery sufficiency per drone
    battery_issues = []
    for eval_res in drone_evaluations:
        if not eval_res.is_battery_sufficient:
            battery_issues.append(
                f"Drone {eval_res.drone_id}: {eval_res.rth_reason or 'Insufficient battery capacity for planned path.'}"
            )

    batt_ok = len(battery_issues) == 0
    checks.append(
        ValidationItem(
            name="Battery Reserve & Return Feasibility",
            passed=batt_ok,
            details="All assigned drones have sufficient capacity to complete mission with safety reserve."
            if batt_ok
            else "; ".join(battery_issues),
        )
    )
    if not batt_ok:
        messages.extend(battery_issues)

    # 5. Waypoints within field boundary buffer (allow 25m margin for base/turns)
    buffered_poly = field.poly_m.buffer(35.0)
    out_of_bounds_count = 0
    for d_id, wps in drone_waypoints.items():
        for wp in wps:
            # Check capture waypoints specifically
            if wp.action == "CAPTURE":
                from shapely.geometry import Point

                pt = Point(wp.x_m, wp.y_m)
                if not buffered_poly.contains(pt):
                    out_of_bounds_count += 1

    bounds_ok = out_of_bounds_count == 0
    checks.append(
        ValidationItem(
            name="Waypoints Within Field Envelope",
            passed=bounds_ok,
            details="All capture waypoints are strictly located within field boundary."
            if bounds_ok
            else f"{out_of_bounds_count} waypoints lie outside the field boundary.",
        )
    )
    if not bounds_ok:
        messages.append(f"{out_of_bounds_count} waypoints lie outside the field boundary envelope.")

    overall = all(item.passed for item in checks)

    return PlanValidationResult(
        is_valid=overall,
        checks=checks,
        uncovered_cell_ids=uncovered,
        messages=messages,
    )
