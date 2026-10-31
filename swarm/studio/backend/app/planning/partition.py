"""Multi-drone workload partitioning for balanced mission time."""

from __future__ import annotations

import math
from typing import List, Tuple
from app.camera.grid import GridCell


def partition_cells_balanced(
    serpentine_cells: List[GridCell],
    num_active_drones: int,
    base_x_m: float,
    base_y_m: float,
    speed_m_s: float = 6.0,
    dwell_s: float = 1.5,
) -> List[List[GridCell]]:
    """Partition serpentine cells into N contiguous chunks with balanced estimated mission time.

    If cells is empty or num_active_drones <= 1, returns appropriate single chunk.
    """
    total = len(serpentine_cells)
    if total == 0 or num_active_drones <= 1:
        return [serpentine_cells] if serpentine_cells else [[]]

    num_chunks = min(num_active_drones, total)

    # Estimate time for any slice of cells
    def estimate_chunk_time(chunk: List[GridCell]) -> float:
        if not chunk:
            return 0.0
        # Transit from base to first cell
        d_out = math.hypot(chunk[0].center_x_m - base_x_m, chunk[0].center_y_m - base_y_m)
        # Transit from last cell to base
        d_back = math.hypot(chunk[-1].center_x_m - base_x_m, chunk[-1].center_y_m - base_y_m)
        # Inter-cell legs
        d_legs = 0.0
        for i in range(len(chunk) - 1):
            dx = chunk[i + 1].center_x_m - chunk[i].center_x_m
            dy = chunk[i + 1].center_y_m - chunk[i].center_y_m
            d_legs += math.hypot(dx, dy)
        transit_time = (d_out + d_legs + d_back) / max(speed_m_s, 1.0)
        capture_time = len(chunk) * dwell_s
        return transit_time + capture_time

    # Approximate target time per drone
    total_est_time = estimate_chunk_time(serpentine_cells)
    target_time = total_est_time / num_chunks

    chunks: List[List[GridCell]] = []
    current_chunk: List[GridCell] = []
    curr_time = 0.0
    remaining_cells = list(serpentine_cells)

    for i in range(num_chunks - 1):
        target_cells_left = len(remaining_cells) - (num_chunks - 1 - i)
        this_chunk: List[GridCell] = []
        while remaining_cells and len(this_chunk) < target_cells_left:
            candidate = this_chunk + [remaining_cells[0]]
            cand_time = estimate_chunk_time(candidate)
            if this_chunk and abs(cand_time - target_time) > abs(estimate_chunk_time(this_chunk) - target_time):
                # Closer to target by stopping here
                break
            this_chunk.append(remaining_cells.pop(0))
        chunks.append(this_chunk)

    # Last chunk gets all remaining
    chunks.append(remaining_cells)

    # Filter out empty chunks if fewer cells than drones
    while len(chunks) < num_active_drones:
        chunks.append([])

    return chunks
