"""Run recording data models for simulation replay and analysis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class CompletionState(str, Enum):
    """Reason simulation run ended."""
    COMPLETE = "COMPLETE"
    INCOMPLETE_UNFINISHED_TASKS = "INCOMPLETE_UNFINISHED_TASKS"
    TIMEOUT = "TIMEOUT"
    ALL_DRONES_FAILED = "ALL_DRONES_FAILED"


@dataclass
class DroneFrame:
    """Snapshot of a drone at time t."""
    id: int
    x: float
    y: float
    energy: float
    status: str
    task_id: Optional[int]


@dataclass
class TaskFrame:
    """Snapshot of a task at time t."""
    id: int
    status: str
    drone_id: Optional[int]


@dataclass
class Frame:
    """Simulation world snapshot at time t."""
    t: float
    drones: list[DroneFrame]
    tasks: list[TaskFrame]


@dataclass
class EventRecord:
    """Historical event entry in recording."""
    t: float
    type: str
    drone_id: Optional[int]
    task_id: Optional[int]
    detail: str


@dataclass
class RunRecording:
    """Complete serialized record of a simulation run."""
    run_id: str
    config_snapshot: dict[str, Any]
    seed: int
    scenario: dict[str, Any]
    frames: list[Frame] = field(default_factory=list)
    events: list[EventRecord] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    completion_state: CompletionState = CompletionState.COMPLETE
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert recording to a JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "config_snapshot": self.config_snapshot,
            "seed": self.seed,
            "scenario": self.scenario,
            "frames": [
                {
                    "t": f.t,
                    "drones": [asdict(d) for d in f.drones],
                    "tasks": [asdict(tk) for tk in f.tasks],
                }
                for f in self.frames
            ],
            "events": [asdict(e) for e in self.events],
            "metrics": self.metrics,
            "completion_state": self.completion_state.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecording:
        """Construct a RunRecording from a dictionary."""
        frames = [
            Frame(
                t=float(f["t"]),
                drones=[DroneFrame(**d) for d in f["drones"]],
                tasks=[TaskFrame(**tk) for tk in f["tasks"]],
            )
            for f in data.get("frames", [])
        ]
        events = [EventRecord(**e) for e in data.get("events", [])]
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            run_id=data["run_id"],
            config_snapshot=data.get("config_snapshot", {}),
            seed=int(data.get("seed", 42)),
            scenario=data.get("scenario", {}),
            frames=frames,
            events=events,
            metrics=data.get("metrics", {}),
            completion_state=CompletionState(data.get("completion_state", CompletionState.COMPLETE.value)),
        )

    def save_json(self, path: str | Path) -> None:
        """Write recording to a JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: str | Path) -> RunRecording:
        """Load recording from a JSON file."""
        target = Path(path)
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
