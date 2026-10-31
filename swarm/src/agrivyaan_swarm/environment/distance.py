"""Distance and spatial geometry utilities."""

import math
from typing import Tuple


def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance in metres between two 2D points (x1, y1) and (x2, y2)."""
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.hypot(dx, dy)
