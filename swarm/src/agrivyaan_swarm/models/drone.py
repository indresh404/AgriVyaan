"""Drone data model and state definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DroneStatus(str, Enum):
    """Lifecycle status of a drone within the simulation."""
    IDLE = "IDLE"
    TRAVELLING = "TRAVELLING"
    INSPECTING = "INSPECTING"
    RETURNING = "RETURNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class Drone:
    """Represents a simulated UAV in the AgriVyaan swarm.

    Units:
        position, home_position: metres (m)
        max_speed_mps: metres per second (m/s)
        energy_capacity_eu, current_energy_eu: Energy Units (EU)
        total_distance_m: metres (m)
        total_energy_used_eu: Energy Units (EU)
    """

    id: int
    position: tuple[float, float]
    home_position: tuple[float, float]
    max_speed_mps: float
    energy_capacity_eu: float
    current_energy_eu: float
    return_reserve_fraction: float
    travel_rate_eu_per_m: float
    current_task_id: Optional[int] = None
    assigned_task_ids: list[int] = field(default_factory=list)
    status: DroneStatus = DroneStatus.IDLE
    comm_lost: bool = False
    total_distance_m: float = 0.0
    total_energy_used_eu: float = 0.0
    completed_task_count: int = 0

    def __post_init__(self) -> None:
        """Validate drone attributes upon creation."""
        if self.id < 0:
            raise ValueError(f"Drone ID must be non-negative, got {self.id}")
        if self.max_speed_mps <= 0:
            raise ValueError(f"max_speed_mps must be positive, got {self.max_speed_mps}")
        if self.energy_capacity_eu <= 0:
            raise ValueError(f"energy_capacity_eu must be positive, got {self.energy_capacity_eu}")
        if not (0.0 <= self.return_reserve_fraction <= 1.0):
            raise ValueError(
                f"return_reserve_fraction must be in [0, 1], got {self.return_reserve_fraction}"
            )
        if self.travel_rate_eu_per_m < 0:
            raise ValueError(f"travel_rate_eu_per_m must be non-negative, got {self.travel_rate_eu_per_m}")
        if self.current_energy_eu < 0 or self.current_energy_eu > self.energy_capacity_eu:
            raise ValueError(
                f"current_energy_eu ({self.current_energy_eu}) must be in [0, {self.energy_capacity_eu}]"
            )
        # Ensure position and home_position are 2-tuples of floats
        self.position = (float(self.position[0]), float(self.position[1]))
        self.home_position = (float(self.home_position[0]), float(self.home_position[1]))

    @property
    def reserve_energy_eu(self) -> float:
        """Return reserve energy floor in EU."""
        return self.return_reserve_fraction * self.energy_capacity_eu

    @property
    def is_eligible_for_task(self) -> bool:
        """A drone is eligible if not failed, not comm_lost, and either IDLE or COMPLETED."""
        if self.status == DroneStatus.FAILED or self.comm_lost:
            return False
        return self.status in (DroneStatus.IDLE, DroneStatus.COMPLETED)
