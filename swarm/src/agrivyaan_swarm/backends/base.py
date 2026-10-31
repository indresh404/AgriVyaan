"""Drone backend abstraction interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple
from agrivyaan_swarm.models.drone import DroneStatus


class DroneBackend(ABC):
    """Abstract interface defining flight and inspection actuation for a drone."""

    @abstractmethod
    def get_position(self) -> Tuple[float, float]:
        """Current 2D position (x, y) in metres."""
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> DroneStatus:
        """Current operational status."""
        raise NotImplementedError

    @abstractmethod
    def goto(self, x: float, y: float) -> None:
        """Command drone to navigate toward coordinates (x, y)."""
        raise NotImplementedError

    @abstractmethod
    def start_inspection(self, duration_s: float, energy_rate_eu_s: float) -> None:
        """Command drone to initiate inspection at current location."""
        raise NotImplementedError

    @abstractmethod
    def step(self, dt: float) -> dict:
        """Advance drone state by dt seconds.

        Returns:
            dict containing movement distance_m, energy_spent_eu, inspection_finished (bool), arrived (bool).
        """
        raise NotImplementedError
