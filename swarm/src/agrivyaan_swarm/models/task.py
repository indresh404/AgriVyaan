"""Task data model and status definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """Lifecycle status of a field inspection task."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    UNREACHABLE = "UNREACHABLE"


@dataclass
class InspectionTask:
    """Represents a suspicious crop zone requiring targeted drone rescan.

    Units:
        position: metres (m)
        duration_s: seconds (s)
        inspection_energy_eu: Energy Units (EU)
    """

    id: int
    position: tuple[float, float]
    priority: float
    uncertainty: float
    expected_gain: float
    duration_s: float
    inspection_energy_eu: float
    status: TaskStatus = TaskStatus.PENDING
    assigned_drone_id: Optional[int] = None
    attempts: int = 0
    source_finding_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate task parameters."""
        if self.id < 0:
            raise ValueError(f"Task ID must be non-negative, got {self.id}")
        if not (0.0 <= self.priority <= 1.0):
            raise ValueError(f"priority must be in [0, 1], got {self.priority}")
        if not (0.0 <= self.uncertainty <= 1.0):
            raise ValueError(f"uncertainty must be in [0, 1], got {self.uncertainty}")
        if not (0.0 <= self.expected_gain <= 1.0):
            raise ValueError(f"expected_gain must be in [0, 1], got {self.expected_gain}")
        if self.duration_s < 0:
            raise ValueError(f"duration_s must be non-negative, got {self.duration_s}")
        if self.inspection_energy_eu < 0:
            raise ValueError(f"inspection_energy_eu must be non-negative, got {self.inspection_energy_eu}")
        if self.attempts < 0:
            raise ValueError(f"attempts must be non-negative, got {self.attempts}")
        self.position = (float(self.position[0]), float(self.position[1]))
