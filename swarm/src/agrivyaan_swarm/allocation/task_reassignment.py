"""Task reassignment logic following drone failure or comm loss."""

from __future__ import annotations

from typing import Dict, List
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus
from agrivyaan_swarm.simulation.battery import is_task_feasible


def release_failed_drone_tasks(
    failed_drone_id: int,
    tasks: Dict[int, InspectionTask],
    max_attempts: int = 3,
) -> List[int]:
    """Release assigned or in-progress tasks belonging to a failed drone.

    Tasks are reverted to PENDING with attempts incremented.
    If attempts exceed max_attempts, task becomes UNREACHABLE.
    Returns list of released task IDs.
    """
    released: List[int] = []

    for task in tasks.values():
        if task.assigned_drone_id == failed_drone_id and task.status in (
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
        ):
            task.attempts += 1
            task.assigned_drone_id = None
            if task.attempts >= max_attempts:
                task.status = TaskStatus.UNREACHABLE
            else:
                task.status = TaskStatus.PENDING
            released.append(task.id)

    return released


def classify_unreachable_tasks(
    drones: Dict[int, Drone],
    tasks: Dict[int, InspectionTask],
    safety_factor: float = 1.1,
) -> List[int]:
    """Classify remaining PENDING tasks at mission end as UNREACHABLE if infeasible for all surviving drones.

    Rule:
        If there are surviving eligible/return drones, but none can reach the task even from base,
        the task is marked UNREACHABLE.
        If NO surviving non-failed, non-comm-lost drones exist at all, leftover tasks stay PENDING.
    """
    surviving_drones = [
        d for d in drones.values()
        if d.status != DroneStatus.FAILED and not d.comm_lost
    ]

    if not surviving_drones:
        # No eligible drones remain: leave as PENDING
        return []

    marked_unreachable: List[int] = []
    for task in tasks.values():
        if task.status == TaskStatus.PENDING:
            # Check if feasible for at least one surviving drone
            feasible_for_any = any(
                is_task_feasible(drone, task, safety_factor=safety_factor)
                for drone in surviving_drones
            )
            if not feasible_for_any:
                task.status = TaskStatus.UNREACHABLE
                marked_unreachable.append(task.id)

    return marked_unreachable
