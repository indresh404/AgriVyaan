"""Energy model and task feasibility calculations."""

from __future__ import annotations

from typing import Tuple
from agrivyaan_swarm.environment.distance import euclidean_distance
from agrivyaan_swarm.models.drone import Drone
from agrivyaan_swarm.models.task import InspectionTask


def calculate_travel_energy(distance_m: float, travel_rate_eu_per_m: float) -> float:
    """Calculate energy in EU required to travel distance_m at the given rate."""
    return distance_m * travel_rate_eu_per_m


def is_task_feasible(
    drone: Drone,
    task: InspectionTask,
    safety_factor: float = 1.1,
) -> bool:
    """Check if drone has sufficient energy to reach task, inspect it, and return to base.

    Formula:
        E - safety_factor * travel(p -> k) - inspect_k - safety_factor * travel(k -> base) >= reserve_energy
    """
    dist_to_task = euclidean_distance(drone.position, task.position)
    dist_task_to_base = euclidean_distance(task.position, drone.home_position)

    travel_to_task_eu = calculate_travel_energy(dist_to_task, drone.travel_rate_eu_per_m)
    travel_to_base_eu = calculate_travel_energy(dist_task_to_base, drone.travel_rate_eu_per_m)

    total_required_eu = (
        safety_factor * travel_to_task_eu
        + task.inspection_energy_eu
        + safety_factor * travel_to_base_eu
    )

    reserve_eu = drone.reserve_energy_eu
    available_eu = drone.current_energy_eu - reserve_eu

    return available_eu >= total_required_eu


def estimate_energy_cost(
    drone_pos: Tuple[float, float],
    task_pos: Tuple[float, float],
    home_pos: Tuple[float, float],
    task_energy_eu: float,
    travel_rate_eu_per_m: float,
) -> float:
    """Estimate total non-safety-factored energy cost for visiting, inspecting, and returning."""
    dist_to_task = euclidean_distance(drone_pos, task_pos)
    dist_task_to_base = euclidean_distance(task_pos, home_pos)
    return (dist_to_task + dist_task_to_base) * travel_rate_eu_per_m + task_energy_eu
