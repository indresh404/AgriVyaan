"""Simulation engine coordinating drones, tasks, physics, and events."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from agrivyaan_swarm.allocation.base import Allocator
from agrivyaan_swarm.allocation.greedy_allocator import GreedyAllocator
from agrivyaan_swarm.allocation.task_reassignment import (
    classify_unreachable_tasks,
    release_failed_drone_tasks,
)
from agrivyaan_swarm.backends.sim_backend import SimBackend
from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.environment.distance import euclidean_distance
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.recording import (
    CompletionState,
    DroneFrame,
    EventRecord,
    Frame,
    RunRecording,
    TaskFrame,
)
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus
from agrivyaan_swarm.simulation.failure import FailureManager

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Core multi-agent simulation coordinator for virtual drone swarms."""

    def __init__(
        self,
        config: SimulationConfig,
        field: Field,
        allocator: Optional[Allocator] = None,
        run_id: str = "run_001",
    ):
        self.config = config
        self.field = field
        self.allocator = allocator or GreedyAllocator()
        self.run_id = run_id
        self.sim_time = 0.0

        # Initialize drones
        self.drones: Dict[int, Drone] = {}
        self.backends: Dict[int, SimBackend] = {}
        for d_id in range(config.drones.count):
            drone = Drone(
                id=d_id,
                position=config.field.base,
                home_position=config.field.base,
                max_speed_mps=config.drones.speed_mps,
                energy_capacity_eu=config.drones.energy_capacity_eu,
                current_energy_eu=config.drones.energy_capacity_eu,
                return_reserve_fraction=config.drones.return_reserve_fraction,
                travel_rate_eu_per_m=config.drones.travel_rate_eu_per_m,
                status=DroneStatus.IDLE,
            )
            self.drones[d_id] = drone
            self.backends[d_id] = SimBackend(drone)

        # Copy tasks into a dict
        self.tasks: Dict[int, InspectionTask] = {t.id: t for t in field.tasks}

        # Failure manager
        self.failure_mgr = FailureManager(config.failures)

        # Reassignment tracking for recovery metrics
        self.task_release_times: Dict[int, float] = {}
        self.reassigned_tasks_completed: set[int] = set()

        # Recording
        self.events: List[EventRecord] = []
        self.frames: List[Frame] = []

    def log_event(self, event_type: str, drone_id: Optional[int], task_id: Optional[int], detail: str) -> None:
        """Record an event to the chronological event log."""
        self.events.append(
            EventRecord(
                t=round(self.sim_time, 2),
                type=event_type,
                drone_id=drone_id,
                task_id=task_id,
                detail=detail,
            )
        )

    def capture_frame(self) -> None:
        """Record world snapshot at current time."""
        drone_frames = [
            DroneFrame(
                id=d.id,
                x=round(d.position[0], 2),
                y=round(d.position[1], 2),
                energy=round(d.current_energy_eu, 2),
                status=d.status.value,
                task_id=d.current_task_id,
            )
            for d in self.drones.values()
        ]
        task_frames = [
            TaskFrame(
                id=t.id,
                status=t.status.value,
                drone_id=t.assigned_drone_id,
            )
            for t in self.tasks.values()
        ]
        self.frames.append(
            Frame(
                t=round(self.sim_time, 2),
                drones=drone_frames,
                tasks=task_frames,
            )
        )

    def run_allocation_round(self) -> None:
        """Run allocator for eligible drones and dispatch them."""
        assignments = self.allocator.allocate(
            self.drones,
            self.tasks,
            safety_factor=self.config.drones.safety_factor,
        )

        for drone_id, task_id in assignments:
            drone = self.drones[drone_id]
            task = self.tasks[task_id]
            backend = self.backends[drone_id]

            backend.goto(task.position[0], task.position[1])
            self.log_event(
                "TASK_ASSIGNED",
                drone_id=drone_id,
                task_id=task_id,
                detail=f"Drone {drone_id} assigned to task {task_id} at {task.position}",
            )

        # For remaining eligible drones that received no task, direct them back to base
        base_x, base_y = self.config.field.base
        for drone in self.drones.values():
            if drone.is_eligible_for_task and drone.current_task_id is None:
                dist_to_base = euclidean_distance(drone.position, (base_x, base_y))
                if dist_to_base > 1e-4:
                    drone.status = DroneStatus.RETURNING
                    self.backends[drone.id].goto(base_x, base_y)
                    self.log_event(
                        "RETURNING_TO_BASE",
                        drone_id=drone.id,
                        task_id=None,
                        detail=f"Drone {drone.id} returning to base (no feasible tasks)",
                    )
                else:
                    drone.status = DroneStatus.COMPLETED

    def step(self, dt: float) -> bool:
        """Step simulation by dt seconds. Returns True if mission has finished."""
        # 1. Check for failure triggers
        new_failures = self.failure_mgr.check_triggers(self.sim_time, self.drones)
        for drone_id, kind in new_failures:
            drone = self.drones[drone_id]
            if kind == "HARD_FAILURE":
                drone.status = DroneStatus.FAILED
                self.log_event(
                    "FAILURE_TRIGGERED",
                    drone_id=drone_id,
                    task_id=drone.current_task_id,
                    detail=f"Drone {drone_id} suffered HARD_FAILURE and stopped",
                )
            elif kind == "COMM_LOSS":
                drone.comm_lost = True
                self.log_event(
                    "COMM_LOSS_TRIGGERED",
                    drone_id=drone_id,
                    task_id=drone.current_task_id,
                    detail=f"Drone {drone_id} lost communications; continuing autonomously",
                )

        # 2. Poll failure detection actions
        detected_actions = self.failure_mgr.poll_detection_actions(self.sim_time)
        need_reallocation = False
        for action in detected_actions:
            if action.kind == "HARD_FAILURE":
                released_ids = release_failed_drone_tasks(
                    action.drone_id,
                    self.tasks,
                    max_attempts=self.config.simulation.max_task_attempts,
                )
                for tid in released_ids:
                    self.task_release_times[tid] = self.sim_time
                    self.log_event(
                        "TASK_RELEASED",
                        drone_id=action.drone_id,
                        task_id=tid,
                        detail=f"Task {tid} released back to pending after drone {action.drone_id} failure detected",
                    )
                if released_ids:
                    need_reallocation = True

        # 3. Step individual drones
        base_x, base_y = self.config.field.base
        for drone_id, drone in self.drones.items():
            if drone.status == DroneStatus.FAILED:
                continue

            backend = self.backends[drone_id]

            if drone.status == DroneStatus.TRAVELLING:
                res = backend.step(dt)
                if res["arrived"]:
                    if drone.current_task_id is not None:
                        task = self.tasks[drone.current_task_id]
                        task.status = TaskStatus.IN_PROGRESS
                        backend.start_inspection(task.duration_s, self.config.tasks.inspect_rate_eu_per_s)
                        self.log_event(
                            "INSPECTION_STARTED",
                            drone_id=drone_id,
                            task_id=task.id,
                            detail=f"Drone {drone_id} started inspecting task {task.id}",
                        )
                    else:
                        drone.status = DroneStatus.COMPLETED
                        self.log_event(
                            "DRONE_LANDED",
                            drone_id=drone_id,
                            task_id=None,
                            detail=f"Drone {drone_id} landed at base",
                        )
                        if not drone.comm_lost:
                            need_reallocation = True

            elif drone.status == DroneStatus.INSPECTING:
                res = backend.step(dt)
                if res["inspection_finished"]:
                    if drone.current_task_id is not None:
                        task = self.tasks[drone.current_task_id]
                        task.status = TaskStatus.COMPLETED
                        drone.completed_task_count += 1
                        if task.id in self.task_release_times:
                            self.reassigned_tasks_completed.add(task.id)

                        self.log_event(
                            "INSPECTION_COMPLETED",
                            drone_id=drone_id,
                            task_id=task.id,
                            detail=f"Drone {drone_id} completed task {task.id}",
                        )
                        task.assigned_drone_id = drone_id
                        drone.current_task_id = None
                        drone.assigned_task_ids = []

                    if drone.comm_lost:
                        # Autonomous return to base on comms loss
                        drone.status = DroneStatus.RETURNING
                        backend.goto(base_x, base_y)
                        self.log_event(
                            "AUTONOMOUS_RETURN",
                            drone_id=drone_id,
                            task_id=None,
                            detail=f"Comm-lost drone {drone_id} returning to base autonomously",
                        )
                    else:
                        drone.status = DroneStatus.IDLE
                        need_reallocation = True

            elif drone.status == DroneStatus.RETURNING:
                res = backend.step(dt)
                if res["arrived"]:
                    drone.status = DroneStatus.COMPLETED
                    self.log_event(
                        "DRONE_LANDED",
                        drone_id=drone_id,
                        task_id=None,
                        detail=f"Drone {drone_id} landed at base",
                    )
                    if not drone.comm_lost:
                        need_reallocation = True

        # 4. Run allocation round if needed
        if need_reallocation:
            self.run_allocation_round()

        # Check termination condition
        all_drones_finished = True
        for drone in self.drones.values():
            if drone.status not in (DroneStatus.FAILED, DroneStatus.COMPLETED):
                all_drones_finished = False
                break

        return all_drones_finished

    def run(self) -> RunRecording:
        """Execute simulation to completion or timeout."""
        dt = self.config.simulation.dt_s
        max_t = self.config.simulation.max_sim_time_s
        record_interval = self.config.simulation.record_every_n_steps

        self.log_event("MISSION_STARTED", drone_id=None, task_id=None, detail="Simulation mission started")
        self.capture_frame()

        # Initial allocation
        self.run_allocation_round()

        step_count = 0
        while self.sim_time < max_t:
            finished = self.step(dt)
            self.sim_time += dt
            step_count += 1

            if step_count % record_interval == 0:
                self.capture_frame()

            if finished:
                break

        # Ensure final frame is recorded
        self.capture_frame()

        # Determine completion state
        all_failed = all(d.status == DroneStatus.FAILED for d in self.drones.values())
        if all_failed:
            completion_state = CompletionState.ALL_DRONES_FAILED
        elif self.sim_time >= max_t:
            completion_state = CompletionState.TIMEOUT
        else:
            # Classify any remaining unreachable tasks
            classify_unreachable_tasks(self.drones, self.tasks, safety_factor=self.config.drones.safety_factor)
            unfinished_pending = any(t.status == TaskStatus.PENDING for t in self.tasks.values())
            if unfinished_pending:
                completion_state = CompletionState.INCOMPLETE_UNFINISHED_TASKS
            else:
                completion_state = CompletionState.COMPLETE

        self.log_event(
            "MISSION_ENDED",
            drone_id=None,
            task_id=None,
            detail=f"Mission terminated with state: {completion_state.value}",
        )

        scenario_dict = {
            "field": {
                "width_m": self.field.width_m,
                "height_m": self.field.height_m,
                "base_position": list(self.field.base_position),
            },
            "tasks": [
                {
                    "id": t.id,
                    "position": list(t.position),
                    "priority": t.priority,
                    "uncertainty": t.uncertainty,
                    "expected_gain": t.expected_gain,
                    "duration_s": t.duration_s,
                    "inspection_energy_eu": t.inspection_energy_eu,
                    "status": t.status.value,
                }
                for t in self.tasks.values()
            ],
        }

        # Calculate metrics (imported dynamically or via calculations module)
        from agrivyaan_swarm.metrics.calculations import compute_metrics
        metrics = compute_metrics(
            self.sim_time,
            self.drones,
            self.tasks,
            self.events,
            self.task_release_times,
            self.reassigned_tasks_completed,
            completion_state,
        )

        config_dict = {
            "field": {
                "width_m": self.config.field.width_m,
                "height_m": self.config.field.height_m,
                "base": list(self.config.field.base),
            },
            "tasks": {
                "count": self.config.tasks.count,
                "duration_s": list(self.config.tasks.duration_s),
                "inspect_rate_eu_per_s": self.config.tasks.inspect_rate_eu_per_s,
            },
            "drones": {
                "count": self.config.drones.count,
                "speed_mps": self.config.drones.speed_mps,
                "energy_capacity_eu": self.config.drones.energy_capacity_eu,
                "return_reserve_fraction": self.config.drones.return_reserve_fraction,
                "travel_rate_eu_per_m": self.config.drones.travel_rate_eu_per_m,
                "safety_factor": self.config.drones.safety_factor,
            },
            "simulation": {
                "dt_s": self.config.simulation.dt_s,
                "max_sim_time_s": self.config.simulation.max_sim_time_s,
                "seed": self.config.simulation.seed,
                "record_every_n_steps": self.config.simulation.record_every_n_steps,
            },
        }

        return RunRecording(
            run_id=self.run_id,
            config_snapshot=config_dict,
            seed=self.config.simulation.seed,
            scenario=scenario_dict,
            frames=self.frames,
            events=self.events,
            metrics=metrics,
            completion_state=completion_state,
        )
