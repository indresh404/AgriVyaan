"""Tests for metrics computation and invariants."""

from agrivyaan_swarm.metrics.calculations import compute_metrics
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.recording import CompletionState, EventRecord
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def test_hand_calculated_metrics():
    """Verify metrics calculation against exact manual calculations."""
    drone0 = Drone(
        id=0,
        position=(0.0, 0.0),
        home_position=(0.0, 0.0),
        max_speed_mps=5.0,
        energy_capacity_eu=500.0,
        current_energy_eu=400.0,
        return_reserve_fraction=0.2,
        travel_rate_eu_per_m=1.0,
        total_distance_m=100.0,
        total_energy_used_eu=120.0,
        completed_task_count=2,
    )
    drone1 = Drone(
        id=1,
        position=(0.0, 0.0),
        home_position=(0.0, 0.0),
        max_speed_mps=5.0,
        energy_capacity_eu=500.0,
        current_energy_eu=420.0,
        return_reserve_fraction=0.2,
        travel_rate_eu_per_m=1.0,
        total_distance_m=60.0,
        total_energy_used_eu=80.0,
        completed_task_count=1,
    )
    drones = {0: drone0, 1: drone1}

    # Tasks: total 4 tasks, 3 completed, 1 unfinished
    # Priorities: 0.8, 0.6, 0.4 (completed) => sum = 1.8
    # 0.2 (unfinished) => total priority = 2.0
    # Expected priority-weighted coverage = 1.8 / 2.0 = 0.90
    tasks = {
        0: InspectionTask(id=0, position=(10, 10), priority=0.8, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.COMPLETED),
        1: InspectionTask(id=1, position=(20, 20), priority=0.6, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.COMPLETED),
        2: InspectionTask(id=2, position=(30, 30), priority=0.4, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.COMPLETED),
        3: InspectionTask(id=3, position=(40, 40), priority=0.2, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.PENDING),
    }

    events = [
        EventRecord(t=10.0, type="INSPECTION_COMPLETED", drone_id=0, task_id=0, detail="Done"),
        EventRecord(t=25.0, type="INSPECTION_COMPLETED", drone_id=0, task_id=1, detail="Done"),
        EventRecord(t=35.0, type="INSPECTION_COMPLETED", drone_id=1, task_id=2, detail="Done"),
    ]

    metrics = compute_metrics(
        makespan_s=50.0,
        drones=drones,
        tasks=tasks,
        events=events,
        task_release_times={},
        reassigned_tasks_completed=set(),
        completion_state=CompletionState.COMPLETE,
    )

    assert metrics["makespan_s"] == 50.0
    assert metrics["total_distance_m"] == 160.0
    assert metrics["total_energy_eu"] == 200.0
    # 200 / 3 completed = 66.667
    assert abs(metrics["energy_per_completed_task_eu"] - 66.667) < 1e-2
    assert metrics["completed_tasks_count"] == 3
    assert metrics["unfinished_tasks_count"] == 1
    assert metrics["priority_weighted_coverage"] == 0.9
    assert metrics["duplicate_assignments"] == 0
    assert metrics["battery_reserve_violations"] == 0


def test_zero_priority_and_no_task_edge_cases():
    """Verify coverage handling when total priority is 0 or task count is 0."""
    drone0 = Drone(
        id=0,
        position=(0.0, 0.0),
        home_position=(0.0, 0.0),
        max_speed_mps=5.0,
        energy_capacity_eu=500.0,
        current_energy_eu=400.0,
        return_reserve_fraction=0.2,
        travel_rate_eu_per_m=1.0,
    )
    drones = {0: drone0}

    # Case 1: No tasks
    m_no_tasks = compute_metrics(
        makespan_s=10.0,
        drones=drones,
        tasks={},
        events=[],
        task_release_times={},
        reassigned_tasks_completed=set(),
        completion_state=CompletionState.COMPLETE,
    )
    assert m_no_tasks["priority_weighted_coverage"] == "n/a"

    # Case 2: Zero priority tasks (fallback to unweighted ratio)
    tasks_zero_p = {
        0: InspectionTask(id=0, position=(10, 10), priority=0.0, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.COMPLETED),
        1: InspectionTask(id=1, position=(20, 20), priority=0.0, uncertainty=0.5, expected_gain=0.6, duration_s=10, inspection_energy_eu=5, status=TaskStatus.PENDING),
    }
    m_zero_p = compute_metrics(
        makespan_s=10.0,
        drones=drones,
        tasks=tasks_zero_p,
        events=[],
        task_release_times={},
        reassigned_tasks_completed=set(),
        completion_state=CompletionState.COMPLETE,
    )
    # 1 of 2 completed => 0.5
    assert m_zero_p["priority_weighted_coverage"] == 0.5
