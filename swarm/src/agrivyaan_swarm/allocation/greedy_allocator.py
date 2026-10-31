"""Greedy nearest-task allocator baseline."""

from __future__ import annotations

from typing import Dict, List, Tuple
from agrivyaan_swarm.allocation.base import Allocator
from agrivyaan_swarm.environment.distance import euclidean_distance
from agrivyaan_swarm.models.drone import Drone
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus
from agrivyaan_swarm.simulation.battery import is_task_feasible


class GreedyAllocator(Allocator):
    """Assigns nearest feasible pending task to eligible drones sequentially by drone ID.

    Bias note:
        Iterating drones sequentially in ascending drone ID order introduces a mild
        first-drone-first priority bias. Drones with lower IDs get first pick of the
        spatially nearest tasks.
    """

    def allocate(
        self,
        drones: Dict[int, Drone],
        tasks: Dict[int, InspectionTask],
        safety_factor: float = 1.1,
    ) -> List[Tuple[int, int]]:
        assignments: List[Tuple[int, int]] = []

        # Find eligible drones sorted by ID
        eligible_drones = [d for d in drones.values() if d.is_eligible_for_task]
        eligible_drones.sort(key=lambda d: d.id)

        for drone in eligible_drones:
            # Pending tasks
            pending_tasks = [t for t in tasks.values() if t.status == TaskStatus.PENDING]
            if not pending_tasks:
                break

            # Find feasible candidate tasks
            feasible_tasks = [
                t for t in pending_tasks
                if is_task_feasible(drone, t, safety_factor=safety_factor)
            ]
            if not feasible_tasks:
                continue

            # Sort by distance to drone, ties broken by task ID
            feasible_tasks.sort(
                key=lambda t: (euclidean_distance(drone.position, t.position), t.id)
            )

            chosen_task = feasible_tasks[0]

            # Mark task assigned immediately to prevent duplicate allocation
            chosen_task.status = TaskStatus.ASSIGNED
            chosen_task.assigned_drone_id = drone.id

            drone.current_task_id = chosen_task.id
            drone.assigned_task_ids = [chosen_task.id]

            assignments.append((drone.id, chosen_task.id))

        return assignments
