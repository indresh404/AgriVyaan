"""Failure injection models and trigger evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from agrivyaan_swarm.config import FailureConfig
from agrivyaan_swarm.models.drone import Drone, DroneStatus


@dataclass
class PendingFailureAction:
    """Action to execute when failure detection delay elapses."""
    t_trigger: float
    t_detection: float
    drone_id: int
    kind: str
    executed: bool = False


class FailureManager:
    """Manages failure triggers and pending detection delays."""

    def __init__(self, failure_configs: List[FailureConfig]):
        self.configs = failure_configs
        self.triggered_drone_ids: set[int] = set()
        self.pending_actions: List[PendingFailureAction] = []
        self.failure_times: Dict[int, float] = {}

    def check_triggers(
        self,
        sim_time: float,
        drones: Dict[int, Drone],
    ) -> List[tuple[int, str]]:
        """Evaluate triggers at current simulation step.

        Returns list of (drone_id, kind) for freshly triggered failures.
        """
        freshly_triggered = []

        for cfg in self.configs:
            if cfg.drone_id in self.triggered_drone_ids:
                continue
            drone = drones.get(cfg.drone_id)
            if not drone:
                continue

            should_trigger = False
            if cfg.trigger.type == "time":
                if cfg.trigger.t is not None and sim_time >= cfg.trigger.t:
                    should_trigger = True
            elif cfg.trigger.type == "after_tasks":
                if cfg.trigger.task_count is not None and drone.completed_task_count >= cfg.trigger.task_count:
                    should_trigger = True

            if should_trigger:
                self.triggered_drone_ids.add(cfg.drone_id)
                self.failure_times[cfg.drone_id] = sim_time
                self.pending_actions.append(
                    PendingFailureAction(
                        t_trigger=sim_time,
                        t_detection=sim_time + cfg.detection_delay_s,
                        drone_id=cfg.drone_id,
                        kind=cfg.kind,
                    )
                )
                freshly_triggered.append((cfg.drone_id, cfg.kind))

        return freshly_triggered

    def poll_detection_actions(self, sim_time: float) -> List[PendingFailureAction]:
        """Return pending failure actions whose detection delay has elapsed."""
        ready = []
        for action in self.pending_actions:
            if not action.executed and sim_time >= action.t_detection:
                action.executed = True
                ready.append(action)
        return ready
