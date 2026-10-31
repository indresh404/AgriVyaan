"""Tests for energy calculations and task feasibility."""

from agrivyaan_swarm.models.drone import Drone, DroneStatus
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus
from agrivyaan_swarm.simulation.battery import calculate_travel_energy, is_task_feasible


def test_hand_calculated_feasibility():
    """Verify feasibility formula against exact hand-calculated figures.

    Parameters:
        Drone base: (0, 0), pos: (0, 0)
        Capacity: 500 EU, current: 500 EU, reserve_fraction: 0.2 => reserve: 100 EU
        Travel rate: 1.0 EU/m, Safety factor: 1.1
        Task at: (30, 40) => dist = 50 m
        Inspection energy: 10 EU
        Required: 1.1 * 50 + 10 + 1.1 * 50 = 120 EU.
        With current_energy = 500 EU: available = 400 EU >= 120 EU => FEASIBLE.
        With current_energy = 215 EU: available = 115 EU < 120 EU => INFEASIBLE.
    """
    drone = Drone(
        id=0,
        position=(0.0, 0.0),
        home_position=(0.0, 0.0),
        max_speed_mps=5.0,
        energy_capacity_eu=500.0,
        current_energy_eu=500.0,
        return_reserve_fraction=0.2,
        travel_rate_eu_per_m=1.0,
    )

    task = InspectionTask(
        id=0,
        position=(30.0, 40.0),
        priority=0.8,
        uncertainty=0.5,
        expected_gain=0.6,
        duration_s=20.0,
        inspection_energy_eu=10.0,
    )

    assert is_task_feasible(drone, task, safety_factor=1.1) is True

    # Reduce energy below requirement (100 reserve + 120 required = 220 threshold)
    drone.current_energy_eu = 215.0
    assert is_task_feasible(drone, task, safety_factor=1.1) is False

    # Exactly at threshold (220.0 EU)
    drone.current_energy_eu = 220.0
    assert is_task_feasible(drone, task, safety_factor=1.1) is True


def test_travel_energy_calculation():
    """Verify linear travel energy calculation."""
    assert calculate_travel_energy(100.0, 1.5) == 150.0
    assert calculate_travel_energy(0.0, 1.5) == 0.0
