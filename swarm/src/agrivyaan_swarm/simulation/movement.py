"""Kinematics and movement update functions."""

from __future__ import annotations

import math
from typing import Tuple
from agrivyaan_swarm.environment.distance import euclidean_distance


def step_movement(
    current_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    speed_mps: float,
    dt: float,
    arrival_threshold_m: float = 1e-4,
) -> Tuple[Tuple[float, float], float, bool]:
    """Advance position toward target at speed_mps for dt seconds without overshooting.

    Returns:
        (new_position, distance_moved, arrived)
    """
    dist_remaining = euclidean_distance(current_pos, target_pos)
    if dist_remaining <= arrival_threshold_m:
        return (target_pos, 0.0, True)

    step_dist = speed_mps * dt

    if step_dist >= dist_remaining:
        # Snap directly to target to avoid overshoot
        return (target_pos, dist_remaining, True)

    ratio = step_dist / dist_remaining
    new_x = current_pos[0] + ratio * (target_pos[0] - current_pos[0])
    new_y = current_pos[1] + ratio * (target_pos[1] - current_pos[1])

    return ((new_x, new_y), step_dist, False)
