"""Base task allocator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List
from agrivyaan_swarm.models.drone import Drone
from agrivyaan_swarm.models.task import InspectionTask


class Allocator(ABC):
    """Abstract interface for task allocation algorithms."""

    @abstractmethod
    def allocate(
        self,
        drones: Dict[int, Drone],
        tasks: Dict[int, InspectionTask],
        safety_factor: float = 1.1,
    ) -> List[tuple[int, int]]:
        """Assign pending feasible tasks to eligible drones.

        Returns:
            List of (drone_id, task_id) assignments.
        """
        raise NotImplementedError
