"""Boustrophedon serpentine path generation and manual waypoint handling."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel

from app.camera.grid import GridCell
from app.geo.projection import LocalProjection


class Waypoint(BaseModel):
    index: int
    cell_id: Optional[str] = None
    lat: float
    lon: float
    x_m: float
    y_m: float
    altitude_m: float
    action: str = "PASS"  # "TAKEOFF", "CAPTURE", "PASS", "RTH", "LAND", "HANDOVER"


def sort_cells_boustrophedon(cells: List[GridCell]) -> List[GridCell]:
    """Order cells in serpentine boustrophedon sequence by row and alternating columns."""
    if not cells:
        return []

    # Group cells by row
    rows_dict: Dict[int, List[GridCell]] = {}
    for cell in cells:
        rows_dict.setdefault(cell.row, []).append(cell)

    sorted_rows = sorted(rows_dict.keys())
    serpentine_cells: List[GridCell] = []

    for i, r in enumerate(sorted_rows):
        row_cells = rows_dict[r]
        # Even iteration index: left to right (col asc); odd: right to left (col desc)
        if i % 2 == 0:
            row_cells.sort(key=lambda c: c.col)
        else:
            row_cells.sort(key=lambda c: c.col, reverse=True)
        serpentine_cells.extend(row_cells)

    return serpentine_cells


def build_drone_path(
    cells_chunk: List[GridCell],
    base_lat: float,
    base_lon: float,
    altitude_m: float,
    proj: LocalProjection,
) -> List[Waypoint]:
    """Build a complete flight path from base -> capture cells -> base."""
    base_x, base_y = proj.forward(base_lon, base_lat)
    waypoints: List[Waypoint] = []

    # 1. Takeoff from base
    waypoints.append(
        Waypoint(
            index=0,
            cell_id=None,
            lat=round(base_lat, 7),
            lon=round(base_lon, 7),
            x_m=round(base_x, 2),
            y_m=round(base_y, 2),
            altitude_m=round(altitude_m, 2),
            action="TAKEOFF",
        )
    )

    # 2. Sequence of cell captures
    idx = 1
    for cell in cells_chunk:
        waypoints.append(
            Waypoint(
                index=idx,
                cell_id=cell.cell_id,
                lat=cell.center_lat,
                lon=cell.center_lon,
                x_m=cell.center_x_m,
                y_m=cell.center_y_m,
                altitude_m=round(altitude_m, 2),
                action="CAPTURE",
            )
        )
        idx += 1

    # 3. Return to base and Land
    waypoints.append(
        Waypoint(
            index=idx,
            cell_id=None,
            lat=round(base_lat, 7),
            lon=round(base_lon, 7),
            x_m=round(base_x, 2),
            y_m=round(base_y, 2),
            altitude_m=round(altitude_m, 2),
            action="RTH",
        )
    )
    waypoints.append(
        Waypoint(
            index=idx + 1,
            cell_id=None,
            lat=round(base_lat, 7),
            lon=round(base_lon, 7),
            x_m=round(base_x, 2),
            y_m=round(base_y, 2),
            altitude_m=0.0,
            action="LAND",
        )
    )

    return waypoints
