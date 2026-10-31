"""Time, flight kinematics, and battery energy calculations."""

from __future__ import annotations

import math
from typing import List, Tuple
from pydantic import BaseModel, Field

from app.planning.path import Waypoint


class DroneBatteryProfile(BaseModel):
    capacity_Wh: float = 74.0
    power_hover_W: float = 150.0
    power_cruise_W: float = 160.0
    power_climb_W: float = 220.0
    reserve_pct: float = 25.0
    initial_charge_pct: float = 100.0
    drain_multiplier: float = 1.0
    speed_m_s: float = 6.0
    climb_rate_m_s: float = 3.0
    descent_rate_m_s: float = 2.5
    dwell_time_s: float = 1.5
    turn_penalty_s: float = 2.0
    turn_angle_threshold_deg: float = 30.0
    safety_factor: float = 1.2


class PathEvaluationResult(BaseModel):
    drone_id: int
    num_waypoints: int
    num_captures: int
    path_length_m: float
    climb_time_s: float
    cruise_time_s: float
    hover_time_s: float
    descent_time_s: float
    total_time_s: float
    total_time_min: float
    energy_used_Wh: float
    remaining_Wh: float
    remaining_battery_pct: float
    is_battery_sufficient: bool
    earliest_rth_waypoint_index: int = -1
    rth_reason: str = ""


def heading_between(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate heading in degrees from (x1, y1) to (x2, y2). 0 = North, 90 = East."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    deg = math.degrees(math.atan2(dx, dy)) % 360.0
    return deg


def evaluate_flight_plan(
    drone_id: int,
    waypoints: List[Waypoint],
    profile: DroneBatteryProfile,
    altitude_m: float,
) -> PathEvaluationResult:
    """Evaluate path kinematics, timing, and energy consumption step-by-step."""
    if len(waypoints) < 2:
        return PathEvaluationResult(
            drone_id=drone_id,
            num_waypoints=len(waypoints),
            num_captures=0,
            path_length_m=0.0,
            climb_time_s=0.0,
            cruise_time_s=0.0,
            hover_time_s=0.0,
            descent_time_s=0.0,
            total_time_s=0.0,
            total_time_min=0.0,
            energy_used_Wh=0.0,
            remaining_Wh=profile.capacity_Wh * (profile.initial_charge_pct / 100.0),
            remaining_battery_pct=profile.initial_charge_pct,
            is_battery_sufficient=True,
        )

    # 1. Takeoff & Climb
    t_climb = altitude_m / max(profile.climb_rate_m_s, 0.5)
    t_descent = altitude_m / max(profile.descent_rate_m_s, 0.5)

    t_cruise = 0.0
    t_hover = 0.0
    total_dist_m = 0.0
    num_captures = 0

    curr_heading = 0.0
    has_prev_heading = False

    # Track energy consumption along waypoints to check reserve feasibility
    current_capacity = profile.capacity_Wh * (profile.initial_charge_pct / 100.0)
    e_used_Wh = (profile.power_climb_W * t_climb) / 3600.0
    reserve_Wh = profile.capacity_Wh * (profile.reserve_pct / 100.0)

    insufficient_at_idx = -1
    rth_reason = ""

    # Base coords are at waypoints[0]
    base_pt = (waypoints[0].x_m, waypoints[0].y_m)

    for i in range(len(waypoints) - 1):
        w1 = waypoints[i]
        w2 = waypoints[i + 1]

        leg_dist = math.hypot(w2.x_m - w1.x_m, w2.y_m - w1.y_m)
        total_dist_m += leg_dist
        leg_t = leg_dist / max(profile.speed_m_s, 0.5)
        t_cruise += leg_t

        leg_energy = (profile.power_cruise_W * leg_t) / 3600.0

        # Turn penalty
        turn_t = 0.0
        if leg_dist > 0.1:
            new_heading = heading_between((w1.x_m, w1.y_m), (w2.x_m, w2.y_m))
            if has_prev_heading:
                diff = abs((new_heading - curr_heading + 180.0) % 360.0 - 180.0)
                if diff > profile.turn_angle_threshold_deg:
                    turn_t = profile.turn_penalty_s
            curr_heading = new_heading
            has_prev_heading = True

        # Dwell time on captures
        dwell_t = 0.0
        if w2.action == "CAPTURE":
            dwell_t = profile.dwell_time_s
            num_captures += 1

        hover_leg_t = turn_t + dwell_t
        t_hover += hover_leg_t
        hover_energy = (profile.power_hover_W * hover_leg_t) / 3600.0

        e_used_Wh += (leg_energy + hover_energy) * profile.drain_multiplier

        # Check return feasibility from w2 back to base
        dist_to_base = math.hypot(w2.x_m - base_pt[0], w2.y_m - base_pt[1])
        t_return_cruise = dist_to_base / max(profile.speed_m_s, 0.5)
        e_return_Wh = (
            (profile.power_cruise_W * t_return_cruise + profile.power_hover_W * t_descent)
            / 3600.0
        ) * profile.drain_multiplier

        remaining_now = current_capacity - e_used_Wh
        if (
            remaining_now - profile.safety_factor * e_return_Wh < reserve_Wh
            and insufficient_at_idx == -1
            and w2.action != "RTH"
            and w2.action != "LAND"
        ):
            insufficient_at_idx = i + 1
            rth_reason = f"Battery drops below safety margin ({profile.reserve_pct}%) at waypoint {i+1} ({w2.cell_id or 'point'})."

    # Add descent hover energy
    e_used_Wh += ((profile.power_hover_W * t_descent) / 3600.0) * profile.drain_multiplier
    t_total = t_climb + t_cruise + t_hover + t_descent

    remaining_Wh = max(0.0, current_capacity - e_used_Wh)
    remaining_pct = max(0.0, (remaining_Wh / profile.capacity_Wh) * 100.0)

    is_sufficient = (remaining_Wh >= reserve_Wh) and (insufficient_at_idx == -1)

    return PathEvaluationResult(
        drone_id=drone_id,
        num_waypoints=len(waypoints),
        num_captures=num_captures,
        path_length_m=round(total_dist_m, 2),
        climb_time_s=round(t_climb, 1),
        cruise_time_s=round(t_cruise, 1),
        hover_time_s=round(t_hover, 1),
        descent_time_s=round(t_descent, 1),
        total_time_s=round(t_total, 1),
        total_time_min=round(t_total / 60.0, 2),
        energy_used_Wh=round(e_used_Wh, 2),
        remaining_Wh=round(remaining_Wh, 2),
        remaining_battery_pct=round(remaining_pct, 1),
        is_battery_sufficient=is_sufficient,
        earliest_rth_waypoint_index=insufficient_at_idx,
        rth_reason=rth_reason,
    )
