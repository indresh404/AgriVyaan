"""Configuration loading, representation, and validation."""

from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple


@dataclass
class FieldConfig:
    width_m: float = 100.0
    height_m: float = 100.0
    base: Tuple[float, float] = (0.0, 0.0)

    def validate(self) -> None:
        if self.width_m <= 0 or self.height_m <= 0:
            raise ValueError(f"Field dimensions must be positive, got {self.width_m}x{self.height_m}")
        bx, by = self.base
        if not (0.0 <= bx <= self.width_m and 0.0 <= by <= self.height_m):
            raise ValueError(f"Field base {self.base} must be within bounds [0, {self.width_m}]x[0, {self.height_m}]")


@dataclass
class TasksConfig:
    count: int = 10
    duration_s: Tuple[float, float] = (10.0, 30.0)
    inspect_rate_eu_per_s: float = 0.5

    def validate(self) -> None:
        if self.count < 0:
            raise ValueError(f"Task count must be non-negative, got {self.count}")
        if self.duration_s[0] < 0 or self.duration_s[1] < self.duration_s[0]:
            raise ValueError(f"Task duration range must be non-negative and min <= max, got {self.duration_s}")
        if self.inspect_rate_eu_per_s < 0:
            raise ValueError(f"inspect_rate_eu_per_s must be non-negative, got {self.inspect_rate_eu_per_s}")


@dataclass
class DronesConfig:
    count: int = 3
    speed_mps: float = 5.0
    energy_capacity_eu: float = 500.0
    return_reserve_fraction: float = 0.2
    travel_rate_eu_per_m: float = 1.0
    safety_factor: float = 1.1

    def validate(self) -> None:
        if self.count <= 0:
            raise ValueError(f"Drone count must be at least 1, got {self.count}")
        if self.speed_mps <= 0:
            raise ValueError(f"speed_mps must be positive, got {self.speed_mps}")
        if self.energy_capacity_eu <= 0:
            raise ValueError(f"energy_capacity_eu must be positive, got {self.energy_capacity_eu}")
        if not (0.0 <= self.return_reserve_fraction <= 1.0):
            raise ValueError(f"return_reserve_fraction must be in [0, 1], got {self.return_reserve_fraction}")
        if self.travel_rate_eu_per_m < 0:
            raise ValueError(f"travel_rate_eu_per_m must be non-negative, got {self.travel_rate_eu_per_m}")
        if self.safety_factor < 1.0:
            raise ValueError(f"safety_factor must be >= 1.0, got {self.safety_factor}")


@dataclass
class FailureTrigger:
    type: str  # "time" or "after_tasks"
    t: Optional[float] = None
    task_count: Optional[int] = None

    def validate(self) -> None:
        if self.type not in ("time", "after_tasks"):
            raise ValueError(f"Unsupported failure trigger type: '{self.type}'. Must be 'time' or 'after_tasks'.")
        if self.type == "time":
            if self.t is None or self.t < 0:
                raise ValueError(f"Time trigger requires non-negative 't', got {self.t}")
        elif self.type == "after_tasks":
            if self.task_count is None or self.task_count <= 0:
                raise ValueError(f"after_tasks trigger requires positive 'task_count', got {self.task_count}")


@dataclass
class FailureConfig:
    drone_id: int
    trigger: FailureTrigger
    kind: str = "HARD_FAILURE"  # "HARD_FAILURE" or "COMM_LOSS"
    detection_delay_s: float = 5.0

    def validate(self) -> None:
        if self.drone_id < 0:
            raise ValueError(f"drone_id must be non-negative, got {self.drone_id}")
        if self.kind not in ("HARD_FAILURE", "COMM_LOSS"):
            raise ValueError(f"Unknown failure kind: '{self.kind}'. Must be 'HARD_FAILURE' or 'COMM_LOSS'.")
        if self.detection_delay_s < 0:
            raise ValueError(f"detection_delay_s must be non-negative, got {self.detection_delay_s}")
        self.trigger.validate()


@dataclass
class SimulationSettings:
    dt_s: float = 0.5
    max_sim_time_s: float = 3600.0
    seed: int = 42
    record_every_n_steps: int = 4
    max_task_attempts: int = 3

    def validate(self) -> None:
        if self.dt_s <= 0:
            raise ValueError(f"dt_s must be positive, got {self.dt_s}")
        if self.max_sim_time_s <= 0:
            raise ValueError(f"max_sim_time_s must be positive, got {self.max_sim_time_s}")
        if self.record_every_n_steps <= 0:
            raise ValueError(f"record_every_n_steps must be positive integer, got {self.record_every_n_steps}")
        if self.max_task_attempts <= 0:
            raise ValueError(f"max_task_attempts must be positive, got {self.max_task_attempts}")


@dataclass
class SimulationConfig:
    field: FieldConfig = dataclasses.field(default_factory=FieldConfig)
    tasks: TasksConfig = dataclasses.field(default_factory=TasksConfig)
    drones: DronesConfig = dataclasses.field(default_factory=DronesConfig)
    simulation: SimulationSettings = dataclasses.field(default_factory=SimulationSettings)
    failures: List[FailureConfig] = dataclasses.field(default_factory=list)
    visualization: dict[str, Any] = dataclasses.field(default_factory=lambda: {"enabled": True})

    def validate(self) -> None:
        self.field.validate()
        self.tasks.validate()
        self.drones.validate()
        self.simulation.validate()
        for f in self.failures:
            f.validate()


def parse_config_dict(data: dict[str, Any]) -> SimulationConfig:
    """Parse raw configuration dictionary into validated SimulationConfig."""
    f_data = data.get("field", {})
    t_data = data.get("tasks", {})
    d_data = data.get("drones", {})
    s_data = data.get("simulation", {})
    fail_data = data.get("failures", [])
    vis_data = data.get("visualization", {"enabled": True})

    # Duration range can be [min, max] or a single number
    dur = t_data.get("duration_s", [10.0, 30.0])
    if isinstance(dur, (int, float)):
        dur_tuple = (float(dur), float(dur))
    elif isinstance(dur, (list, tuple)) and len(dur) == 2:
        dur_tuple = (float(dur[0]), float(dur[1]))
    else:
        raise ValueError(f"Invalid duration_s in config: {dur}")

    base = f_data.get("base", [0.0, 0.0])
    base_tuple = (float(base[0]), float(base[1]))

    field_cfg = FieldConfig(
        width_m=float(f_data.get("width_m", 100.0)),
        height_m=float(f_data.get("height_m", 100.0)),
        base=base_tuple,
    )

    tasks_cfg = TasksConfig(
        count=int(t_data.get("count", 10)),
        duration_s=dur_tuple,
        inspect_rate_eu_per_s=float(t_data.get("inspect_rate_eu_per_s", 0.5)),
    )

    drones_cfg = DronesConfig(
        count=int(d_data.get("count", 3)),
        speed_mps=float(d_data.get("speed_mps", 5.0)),
        energy_capacity_eu=float(d_data.get("energy_capacity_eu", 500.0)),
        return_reserve_fraction=float(d_data.get("return_reserve_fraction", 0.2)),
        travel_rate_eu_per_m=float(d_data.get("travel_rate_eu_per_m", 1.0)),
        safety_factor=float(d_data.get("safety_factor", 1.1)),
    )

    sim_cfg = SimulationSettings(
        dt_s=float(s_data.get("dt_s", 0.5)),
        max_sim_time_s=float(s_data.get("max_sim_time_s", 3600.0)),
        seed=int(s_data.get("seed", 42)),
        record_every_n_steps=int(s_data.get("record_every_n_steps", 4)),
        max_task_attempts=int(s_data.get("max_task_attempts", 3)),
    )

    parsed_failures = []
    for f in fail_data:
        trig = f.get("trigger", {})
        trigger_obj = FailureTrigger(
            type=str(trig.get("type", "time")),
            t=float(trig["t"]) if "t" in trig and trig["t"] is not None else None,
            task_count=int(trig["task_count"]) if "task_count" in trig and trig["task_count"] is not None else None,
        )
        parsed_failures.append(
            FailureConfig(
                drone_id=int(f["drone_id"]),
                trigger=trigger_obj,
                kind=str(f.get("kind", "HARD_FAILURE")),
                detection_delay_s=float(f.get("detection_delay_s", 5.0)),
            )
        )

    cfg = SimulationConfig(
        field=field_cfg,
        tasks=tasks_cfg,
        drones=drones_cfg,
        simulation=sim_cfg,
        failures=parsed_failures,
        visualization=vis_data,
    )
    cfg.validate()
    return cfg


def load_config(path: str | Path) -> SimulationConfig:
    """Load and validate simulation configuration from a JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Configuration file not found at: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_config_dict(data)
