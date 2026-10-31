"""Tests for the GreedyAllocator baseline."""

from agrivyaan_swarm.allocation.greedy_allocator import GreedyAllocator
from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def test_greedy_allocator_no_duplicate_assignment():
    """Verify tasks are assigned at most once across multiple drones."""
    drones = {
        0: Drone(
            id=0,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=500.0,
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
        ),
        1: Drone(
            id=1,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=500.0,
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
        ),
    }

    # Only 1 pending task
    tasks = {
        0: InspectionTask(
            id=0,
            position=(10.0, 10.0),
            priority=0.5,
            uncertainty=0.5,
            expected_gain=0.5,
            duration_s=10.0,
            inspection_energy_eu=5.0,
            status=TaskStatus.PENDING,
        )
    }

    allocator = GreedyAllocator()
    assignments = allocator.allocate(drones, tasks, safety_factor=1.1)

    assert len(assignments) == 1
    drone_id, task_id = assignments[0]
    assert drone_id == 0  # Drone 0 gets it first due to ascending ID order
    assert task_id == 0
    assert tasks[0].status == TaskStatus.ASSIGNED
    assert tasks[0].assigned_drone_id == 0

    # Running allocate again gives no new assignments
    second_round = allocator.allocate(drones, tasks, safety_factor=1.1)
    assert len(second_round) == 0


def test_infeasible_task_not_assigned():
    """Verify a task exceeding battery reserve is not assigned."""
    drones = {
        0: Drone(
            id=0,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=120.0,  # Reserve is 100 EU, only 20 EU available
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
        )
    }
    tasks = {
        0: InspectionTask(
            id=0,
            position=(50.0, 50.0),  # Round trip > 140 m => > 140 EU
            priority=0.9,
            uncertainty=0.5,
            expected_gain=0.8,
            duration_s=20.0,
            inspection_energy_eu=10.0,
            status=TaskStatus.PENDING,
        )
    }

    allocator = GreedyAllocator()
    assignments = allocator.allocate(drones, tasks, safety_factor=1.1)
    assert len(assignments) == 0
    assert tasks[0].status == TaskStatus.PENDING


def test_tie_breaking_by_lowest_task_id():
    """Verify equidistant tasks break ties to lowest task id."""
    drones = {
        0: Drone(
            id=0,
            position=(0.0, 0.0),
            home_position=(0.0, 0.0),
            max_speed_mps=5.0,
            energy_capacity_eu=500.0,
            current_energy_eu=500.0,
            return_reserve_fraction=0.2,
            travel_rate_eu_per_m=1.0,
        )
    }
    # Two tasks at exactly same distance (10m away along axes)
    tasks = {
        5: InspectionTask(
            id=5,
            position=(0.0, 10.0),
            priority=0.5,
            uncertainty=0.5,
            expected_gain=0.5,
            duration_s=5.0,
            inspection_energy_eu=2.5,
            status=TaskStatus.PENDING,
        ),
        2: InspectionTask(
            id=2,
            position=(10.0, 0.0),
            priority=0.5,
            uncertainty=0.5,
            expected_gain=0.5,
            duration_s=5.0,
            inspection_energy_eu=2.5,
            status=TaskStatus.PENDING,
        ),
    }

    allocator = GreedyAllocator()
    assignments = allocator.allocate(drones, tasks, safety_factor=1.1)
    assert len(assignments) == 1
    assert assignments[0] == (0, 2)  # Task 2 chosen over Task 5
