"""Dynamic battery discharge state machine for simulated drones."""

from __future__ import annotations

import math
from app.planning.energy import DroneBatteryProfile


class DroneBatterySim:
    """Tracks battery state and computes energy draw during flight simulation."""

    def __init__(self, profile: DroneBatteryProfile):
        self.profile = profile
        self.capacity_Wh = profile.capacity_Wh
        self.current_Wh = profile.capacity_Wh * (profile.initial_charge_pct / 100.0)
        self.total_energy_used_Wh = 0.0
        self.reserve_Wh = profile.capacity_Wh * (profile.reserve_pct / 100.0)

    @property
    def battery_pct(self) -> float:
        pct = (self.current_Wh / self.capacity_Wh) * 100.0
        return round(max(0.0, min(100.0, pct)), 1)

    def consume(self, state: str, dt_seconds: float):
        """Consume energy based on instantaneous motion state."""
        if state in ("STANDBY", "LANDED"):
            power_w = 0.0
        elif state in ("TAKEOFF", "CLIMB"):
            power_w = self.profile.power_climb_W
        elif state in ("CRUISE", "RTH"):
            power_w = self.profile.power_cruise_W
        else:  # "CAPTURE", "HOVER", "DESCENT", "HANDOVER"
            power_w = self.profile.power_hover_W

        de_Wh = (power_w * dt_seconds * self.profile.drain_multiplier) / 3600.0
        self.current_Wh = max(0.0, self.current_Wh - de_Wh)
        self.total_energy_used_Wh += de_Wh

    def estimate_energy_to_base(self, current_x: float, current_y: float, base_x: float, base_y: float, alt_m: float) -> float:
        """Estimate energy required to return to base and land from current coordinates."""
        dist = math.hypot(current_x - base_x, current_y - base_y)
        t_cruise = dist / max(self.profile.speed_m_s, 0.5)
        t_descent = alt_m / max(self.profile.descent_rate_m_s, 0.5)

        e_cruise = (self.profile.power_cruise_W * t_cruise) / 3600.0
        e_descent = (self.profile.power_hover_W * t_descent) / 3600.0
        return (e_cruise + e_descent) * self.profile.drain_multiplier

    def can_continue(self, current_x: float, current_y: float, base_x: float, base_y: float, alt_m: float) -> bool:
        """Check if remaining energy allows continuing flight while preserving safe return reserve."""
        e_return = self.estimate_energy_to_base(current_x, current_y, base_x, base_y, alt_m)
        safety_energy = e_return * self.profile.safety_factor
        return (self.current_Wh - safety_energy) >= self.reserve_Wh
