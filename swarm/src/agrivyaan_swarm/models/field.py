"""Field and spatial boundary data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from agrivyaan_swarm.models.task import InspectionTask


@dataclass
class Field:
    """Represents the operational field area and base station.

    Units:
        width_m, height_m: metres (m)
        base_position: (x, y) in metres (m)
    """

    width_m: float
    height_m: float
    base_position: tuple[float, float]
    tasks: list[InspectionTask] = field(default_factory=list)
    obstacles: list[Any] = field(default_factory=list)  # Reserved for future collision/obstacle avoidance

    def __post_init__(self) -> None:
        if self.width_m <= 0 or self.height_m <= 0:
            raise ValueError(f"Field dimensions must be positive, got {self.width_m}x{self.height_m}")
        self.base_position = (float(self.base_position[0]), float(self.base_position[1]))
        bx, by = self.base_position
        if not (0.0 <= bx <= self.width_m and 0.0 <= by <= self.height_m):
            raise ValueError(f"Base position {self.base_position} must be within field bounds [0, {self.width_m}]x[0, {self.height_m}]")

    def is_within_bounds(self, point: tuple[float, float]) -> bool:
        """Check if a coordinate point (x, y) is within field bounds."""
        x, y = point
        return 0.0 <= x <= self.width_m and 0.0 <= y <= self.height_m
