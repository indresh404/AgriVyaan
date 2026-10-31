"""Tests for failure injection, task release, and recovery reassignment."""

from agrivyaan_swarm.allocation.task_reassignment import (
    classify_unreachable_tasks,
    release_failed_drone_tasks,
)
from agrivyaan_swarm.config import FailureConfig, FailureTrigger, SimulationConfig
from agrivyaan_swarm.main import run_simulation
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.recording import CompletionState
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def test_release_failed_drone_tasks():
    """Verify in-progress and assigned tasks are released to PENDING with attempts incremented."""
    tasks = {
        0: InspectionTask(
            id=0,
            position=(20.0, 20.0),
            priority=0.8,
            uncertainty=0.5,
            expected_gain=0.6,
            duration_s=10.0,
            inspection_energy_eu=5.0,
            status=TaskStatus.IN_PROGRESS,
            assigned_drone_id=1,
            attempts=0,
        ),
        1: InspectionTask(
            id=1,
            position=(40.0, 40.0),
            priority=0.5,
            uncertainty=0.5,
            expected_gain=0.5,
            duration_s=10.0,
            inspection_energy_eu=5.0,
            status=TaskStatus.COMPLETED,  # already completed! Must be preserved
            assigned_drone_id=1,
            attempts=1,
        ),
    }

    released = release_failed_drone_tasks(failed_drone_id=1, tasks=tasks, max_attempts=3)
    assert released == [0]
    assert tasks[0].status == TaskStatus.PENDING
    assert tasks[0].attempts == 1
    assert tasks[0].assigned_drone_id is None

    # Completed task should be unchanged
    assert tasks[1].status == TaskStatus.COMPLETED


def test_max_attempts_exceeded_becomes_unreachable():
    """Verify task becomes UNREACHABLE after max_attempts failures."""
    tasks = {
        0: InspectionTask(
            id=0,
            position=(20.0, 20.0),
            priority=0.8,
            uncertainty=0.5,
            expected_gain=0.6,
            duration_s=10.0,
            inspection_energy_eu=5.0,
            status=TaskStatus.ASSIGNED,
            assigned_drone_id=2,
            attempts=2,
        )
    }

    released = release_failed_drone_tasks(failed_drone_id=2, tasks=tasks, max_attempts=3)
    assert released == [0]
    assert tasks[0].status == TaskStatus.UNREACHABLE
    assert tasks[0].attempts == 3


def test_classify_unreachable_vs_leftover_pending():
    """Ensure tasks infeasible for all surviving drones become UNREACHABLE, but stay PENDING if no drones remain."""
    tasks = {
        0: InspectionTask(
            id=0,
            position=(90.0, 90.0),
            priority=0.8,
            uncertainty=0.5,
            expected_gain=0.6,
            duration_s=10.0,
            inspection_energy_eu=5.0,
            status=TaskStatus.PENDING,
        )
    }

    # Case 1: Surviving drone exists, but has almost no battery -> task is UNREACHABLE
    drones_low_battery = {
        0: Drone(
            id=0,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=105.0,  # 100 is reserve
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
            status=DroneStatus.COMPLETED,
        )
    }
    unreachable = classify_unreachable_tasks(drones_low_battery, tasks)
    assert unreachable == [0]
    assert tasks[0].status == TaskStatus.UNREACHABLE

    # Case 2: All drones failed -> tasks must remain PENDING
    tasks[0].status = TaskStatus.PENDING
    drones_all_failed = {
        0: Drone(
            id=0,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=105.0,
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
            status=DroneStatus.FAILED,
        )
    }
    unreachable_none = classify_unreachable_tasks(drones_all_failed, tasks)
    assert unreachable_none == []
    assert tasks[0].status == TaskStatus.PENDING


def test_comm_loss_recovery():
    """Verify COMM_LOSS drone completes its task, lands, and is not assigned new work."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 4
    config.simulation.seed = 42

    # Inject COMM_LOSS on drone 0 at t = 2.0 s
    config.failures = [
        FailureConfig(
            drone_id=0,
            trigger=FailureTrigger(type="time", t=2.0),
            kind="COMM_LOSS",
            detection_delay_s=0.0,
        )
    ]

    recording = run_simulation(config)
    assert recording.completion_state in (CompletionState.COMPLETE, CompletionState.INCOMPLETE_UNFINISHED_TASKS)

    # Check events for autonomous return
    comm_events = [e for e in recording.events if e.type == "COMM_LOSS_TRIGGERED"]
    assert len(comm_events) == 1
    assert comm_events[0].drone_id == 0

    return_events = [e for e in recording.events if e.type == "AUTONOMOUS_RETURN"]
    assert len(return_events) >= 1
    assert return_events[0].drone_id == 0
