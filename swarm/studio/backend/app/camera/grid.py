"""Square grid subdivision, clipping, and coverage calculations."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from shapely.geometry import Polygon, box, MultiPolygon
from shapely.affinity import rotate
from shapely.ops import unary_union
from pydantic import BaseModel

from app.geo.polygon import FieldGeometry
from app.camera.footprint import calculate_footprint


class GridCell(BaseModel):
    cell_id: str
    row: int
    col: int
    center_lat: float
    center_lon: float
    center_x_m: float
    center_y_m: float
    polygon_latlon: List[Tuple[float, float]]
    fraction_inside: float


class GridPlanResult(BaseModel):
    altitude_m: float
    cell_side_m: float
    margin: float
    grid_angle_deg: float
    total_cells: int
    kept_cells: int
    field_area_m2: float
    cells_covered_area_m2: float
    coverage_fraction: float
    coverage_pct: float
    cells: List[GridCell]


def generate_grid_plan(
    field: FieldGeometry,
    altitude_m: float,
    margin: float = 0.2,
    grid_angle_deg: float = 0.0,
    min_fraction: float = 0.05,
    sensor_w_mm: float = 6.287,
    sensor_h_mm: float = 4.712,
    focal_length_mm: float = 6.0,
    image_w_px: int = 4056,
    image_h_px: int = 3040,
) -> GridPlanResult:
    """Generate square grid clipped to field polygon and compute coverage."""
    fp = calculate_footprint(
        altitude_m,
        sensor_w_mm=sensor_w_mm,
        sensor_h_mm=sensor_h_mm,
        focal_length_mm=focal_length_mm,
        image_w_px=image_w_px,
        image_h_px=image_h_px,
    )
    cell_side = min(fp.footprint_w_m, fp.footprint_h_m) * (1.0 - margin)
    cell_side = max(cell_side, 1.0)
    cell_area = cell_side * cell_side

    # Rotate field so grid can be generated axis-aligned
    origin = field.poly_m.centroid
    rot_poly = rotate(field.poly_m, -grid_angle_deg, origin=origin)
    minx, miny, maxx, maxy = rot_poly.bounds

    # Calculate rows and columns with slight expansion to cover boundary
    cols = int(math.ceil((maxx - minx) / cell_side))
    rows = int(math.ceil((maxy - miny) / cell_side))

    kept_cells: List[GridCell] = []
    footprint_polys_m = []

    cell_idx = 1
    for r in range(rows):
        y0 = miny + r * cell_side
        y1 = y0 + cell_side
        for c in range(cols):
            x0 = minx + c * cell_side
            x1 = x0 + cell_side

            cell_box = box(x0, y0, x1, y1)
            # Clip against rotated field
            intersection = rot_poly.intersection(cell_box)
            if not intersection.is_empty:
                inter_area = intersection.area
                frac = inter_area / cell_area
                if frac >= min_fraction:
                    # Unrotate cell box back to UTM
                    unrot_cell = rotate(cell_box, grid_angle_deg, origin=origin)
                    cx_m, cy_m = unrot_cell.centroid.x, unrot_cell.centroid.y
                    c_lon, c_lat = field.proj.inverse(cx_m, cy_m)

                    # Exterior lat/lons
                    ext_coords = list(unrot_cell.exterior.coords)
                    poly_latlon = []
                    for mx, my in ext_coords:
                        lon, lat = field.proj.inverse(mx, my)
                        poly_latlon.append((round(lat, 7), round(lon, 7)))

                    cell = GridCell(
                        cell_id=f"C-{cell_idx:02d}",
                        row=r,
                        col=c,
                        center_lat=round(c_lat, 7),
                        center_lon=round(c_lon, 7),
                        center_x_m=round(cx_m, 2),
                        center_y_m=round(cy_m, 2),
                        polygon_latlon=poly_latlon,
                        fraction_inside=round(frac, 4),
                    )
                    kept_cells.append(cell)
                    cell_idx += 1

                    # Actual camera footprint at this waypoint for coverage calculation
                    fp_box = box(
                        cx_m - fp.footprint_w_m / 2.0,
                        cy_m - fp.footprint_h_m / 2.0,
                        cx_m + fp.footprint_w_m / 2.0,
                        cy_m + fp.footprint_h_m / 2.0,
                    )
                    fp_rot = rotate(fp_box, grid_angle_deg, origin=(cx_m, cy_m))
                    footprint_polys_m.append(fp_rot)

    # Compute coverage = area(union of footprints ∩ field) / area(field)
    if footprint_polys_m and field.area_m2 > 0:
        union_fp = unary_union(footprint_polys_m)
        covered_geom = union_fp.intersection(field.poly_m)
        covered_area = covered_geom.area
        cov_frac = min(1.0, covered_area / field.area_m2)
    else:
        covered_area = 0.0
        cov_frac = 0.0

    return GridPlanResult(
        altitude_m=altitude_m,
        cell_side_m=round(cell_side, 2),
        margin=margin,
        grid_angle_deg=grid_angle_deg,
        total_cells=rows * cols,
        kept_cells=len(kept_cells),
        field_area_m2=round(field.area_m2, 2),
        cells_covered_area_m2=round(covered_area, 2),
        coverage_fraction=round(cov_frac, 4),
        coverage_pct=round(cov_frac * 100.0, 2),
        cells=kept_cells,
    )
