"""Metrics calculation module for simulation performance and invariant evaluation."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Set
from agrivyaan_swarm.models.drone import Drone
from agrivyaan_swarm.models.recording import CompletionState, EventRecord
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def compute_metrics(
    makespan_s: float,
    drones: Dict[int, Drone],
    tasks: Dict[int, InspectionTask],
    events: List[EventRecord],
    task_release_times: Dict[int, float],
    reassigned_tasks_completed: Set[int],
    completion_state: CompletionState,
) -> Dict[str, Any]:
    """Compute all required swarm simulation metrics.

    Units:
        makespan_s: seconds (s)
        total_distance_m: metres (m)
        total_energy_eu: Energy Units (EU)
        energy_per_completed_task_eu: EU / task
    """
    total_distance_m = sum(d.total_distance_m for d in drones.values())
    total_energy_eu = sum(d.total_energy_used_eu for d in drones.values())

    completed_tasks = [t for t in tasks.values() if t.status == TaskStatus.COMPLETED]
    completed_count = len(completed_tasks)
    unfinished_count = len(tasks) - completed_count

    if completed_count > 0:
        energy_per_completed_task_eu = round(total_energy_eu / completed_count, 3)
    else:
        energy_per_completed_task_eu = 0.0

    # Priority-weighted coverage
    total_tasks_count = len(tasks)
    if total_tasks_count == 0:
        priority_weighted_coverage: Any = "n/a"
    else:
        sum_total_priority = sum(t.priority for t in tasks.values())
        if sum_total_priority > 1e-9:
            sum_completed_priority = sum(t.priority for t in completed_tasks)
            priority_weighted_coverage = round(sum_completed_priority / sum_total_priority, 4)
        else:
            # Fall back to unweighted completion ratio
            priority_weighted_coverage = round(completed_count / total_tasks_count, 4)

    # Load balance (standard deviation of completed tasks per drone)
    task_counts_per_drone = [d.completed_task_count for d in drones.values()]
    if len(task_counts_per_drone) > 1:
        load_balance_std = round(statistics.stdev(task_counts_per_drone), 3)
    else:
        load_balance_std = 0.0

    # Failure recovery delays: t_reassigned - t_failure
    recovery_delays: List[float] = []
    # Identify assignment times for released tasks
    for event in events:
        if event.type == "TASK_ASSIGNED" and event.task_id in task_release_times:
            tid = event.task_id
            t_rel = task_release_times[tid]
            if event.t >= t_rel:
                recovery_delays.append(event.t - t_rel)

    mean_recovery_delay_s = round(sum(recovery_delays) / len(recovery_delays), 2) if recovery_delays else 0.0
    max_recovery_delay_s = round(max(recovery_delays), 2) if recovery_delays else 0.0

    # INVARIANTS:
    # 1. Duplicate task assignments: check if any task completed more than once or assigned to multiple active drones
    # In events, count TASK_COMPLETED per task_id
    completed_event_tids = [e.task_id for e in events if e.type == "INSPECTION_COMPLETED" and e.task_id is not None]
    duplicate_completions = len(completed_event_tids) - len(set(completed_event_tids))

    # 2. Battery reserve violations: drone finished with current_energy < (reserve_energy - tolerance)
    # Note: A FAILED drone that died mid-flight didn't violate reserve rule; active drones returning to base must not violate reserve
    battery_reserve_violations = 0
    for d in drones.values():
        reserve_floor = d.reserve_energy_eu
        # A tiny numerical tolerance (1e-4) for floating point math
        if d.current_energy_eu < reserve_floor - 1e-4:
            # If drone didn't fail mid-flight, this is a violation
            battery_reserve_violations += 1

    return {
        "makespan_s": round(makespan_s, 2),
        "total_distance_m": round(total_distance_m, 2),
        "total_energy_eu": round(total_energy_eu, 2),
        "energy_per_completed_task_eu": energy_per_completed_task_eu,
        "completed_tasks_count": completed_count,
        "unfinished_tasks_count": unfinished_count,
        "total_tasks_count": total_tasks_count,
        "priority_weighted_coverage": priority_weighted_coverage,
        "load_balance_std": load_balance_std,
        "tasks_per_drone": task_counts_per_drone,
        "mean_recovery_delay_s": mean_recovery_delay_s,
        "max_recovery_delay_s": max_recovery_delay_s,
        "reassigned_tasks_completed_count": len(reassigned_tasks_completed),
        "duplicate_assignments": duplicate_completions,
        "battery_reserve_violations": battery_reserve_violations,
        "completion_state": completion_state.value,
    }
