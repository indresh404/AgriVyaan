"""Simulation state representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from agrivyaan_swarm.models.drone import Drone
from agrivyaan_swarm.models.task import InspectionTask


class MissionState(str, Enum):
    """Overall state of the swarm mission."""
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"


@dataclass
class SimEvent:
    """An event logged during simulation execution."""
    t: float
    type: str
    drone_id: int | None
    task_id: int | None
    detail: str


@dataclass
class SimulationState:
    """Mutable runtime state of the active simulation."""
    time: float
    drones: dict[int, Drone]
    tasks: dict[int, InspectionTask]
    events: list[SimEvent] = field(default_factory=list)
    mission_state: MissionState = MissionState.INITIALIZED
    config: dict[str, Any] = field(default_factory=dict)
    seed: int = 42

    def add_event(self, t: float, event_type: str, drone_id: int | None, task_id: int | None, detail: str) -> None:
        """Add an event to the simulation log."""
        self.events.append(SimEvent(t=round(t, 3), type=event_type, drone_id=drone_id, task_id=task_id, detail=detail))
