"""Simulated drone backend implementing DroneBackend interface."""

from __future__ import annotations

from typing import Optional, Tuple
from agrivyaan_swarm.backends.base import DroneBackend
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.simulation.movement import step_movement


class SimBackend(DroneBackend):
    """Software simulation backend for a virtual drone."""

    def __init__(self, drone: Drone):
        self.drone = drone
        self.target_position: Optional[Tuple[float, float]] = None
        self.remaining_inspection_s: float = 0.0
        self.inspect_rate_eu_s: float = 0.0

    def get_position(self) -> Tuple[float, float]:
        return self.drone.position

    def get_status(self) -> DroneStatus:
        return self.drone.status

    def goto(self, x: float, y: float) -> None:
        self.target_position = (x, y)
        if self.drone.status not in (DroneStatus.RETURNING, DroneStatus.FAILED):
            self.drone.status = DroneStatus.TRAVELLING

    def start_inspection(self, duration_s: float, energy_rate_eu_s: float) -> None:
        self.remaining_inspection_s = duration_s
        self.inspect_rate_eu_s = energy_rate_eu_s
        self.drone.status = DroneStatus.INSPECTING

    def step(self, dt: float) -> dict:
        """Step physics/energy for dt seconds."""
        if self.drone.status == DroneStatus.FAILED:
            return {"distance_m": 0.0, "energy_spent_eu": 0.0, "inspection_finished": False, "arrived": False}

        if self.drone.status in (DroneStatus.TRAVELLING, DroneStatus.RETURNING):
            if self.target_position is None:
                return {"distance_m": 0.0, "energy_spent_eu": 0.0, "inspection_finished": False, "arrived": True}

            new_pos, dist_moved, arrived = step_movement(
                self.drone.position,
                self.target_position,
                self.drone.max_speed_mps,
                dt,
            )
            energy_used = dist_moved * self.drone.travel_rate_eu_per_m
            self.drone.position = new_pos
            self.drone.total_distance_m += dist_moved
            self.drone.total_energy_used_eu += energy_used
            self.drone.current_energy_eu = max(0.0, self.drone.current_energy_eu - energy_used)

            return {
                "distance_m": dist_moved,
                "energy_spent_eu": energy_used,
                "inspection_finished": False,
                "arrived": arrived,
            }

        if self.drone.status == DroneStatus.INSPECTING:
            step_inspect_time = min(dt, self.remaining_inspection_s)
            energy_used = step_inspect_time * self.inspect_rate_eu_s
            self.remaining_inspection_s -= step_inspect_time
            self.drone.total_energy_used_eu += energy_used
            self.drone.current_energy_eu = max(0.0, self.drone.current_energy_eu - energy_used)

            finished = self.remaining_inspection_s <= 1e-6
            return {
                "distance_m": 0.0,
                "energy_spent_eu": energy_used,
                "inspection_finished": finished,
                "arrived": False,
            }

        return {"distance_m": 0.0, "energy_spent_eu": 0.0, "inspection_finished": False, "arrived": False}
