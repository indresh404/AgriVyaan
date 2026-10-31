"""Polygon geometry analysis and illustrative crop-row generation."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple
from shapely.geometry import Polygon, MultiLineString, LineString, box
from shapely.affinity import rotate

from app.geo.projection import LocalProjection


class FieldGeometry:
    """Encapsulates a field polygon in both WGS84 and local metric UTM."""

    def __init__(self, latlon_coords: List[Tuple[float, float]]):
        if len(latlon_coords) < 3:
            raise ValueError("Polygon must have at least 3 vertices.")
        self.latlon_coords = latlon_coords

        # Compute centroid to determine local UTM projection
        mean_lat = sum(p[0] for p in latlon_coords) / len(latlon_coords)
        mean_lon = sum(p[1] for p in latlon_coords) / len(latlon_coords)
        self.proj = LocalProjection(mean_lat, mean_lon)

        # Build metric Shapely polygon
        metric_coords = [self.proj.forward(lon, lat) for lat, lon in latlon_coords]
        self.poly_m = Polygon(metric_coords)
        if not self.poly_m.is_valid:
            self.poly_m = self.poly_m.buffer(0)

    @property
    def area_m2(self) -> float:
        return float(self.poly_m.area)

    @property
    def area_ha(self) -> float:
        return self.area_m2 / 10000.0

    @property
    def area_acres(self) -> float:
        return self.area_m2 * 0.000247105

    @property
    def perimeter_m(self) -> float:
        return float(self.poly_m.length)

    @property
    def centroid_latlon(self) -> Tuple[float, float]:
        cx, cy = self.poly_m.centroid.x, self.poly_m.centroid.y
        lon, lat = self.proj.inverse(cx, cy)
        return round(lat, 7), round(lon, 7)

    @property
    def bounds_m(self) -> Tuple[float, float, float, float]:
        """(minx, miny, maxx, maxy) in metres."""
        return self.poly_m.bounds

    @property
    def bounds_latlon(self) -> Dict[str, float]:
        minx, miny, maxx, maxy = self.bounds_m
        min_lon, min_lat = self.proj.inverse(minx, miny)
        max_lon, max_lat = self.proj.inverse(maxx, maxy)
        return {
            "south": min(min_lat, max_lat),
            "north": max(min_lat, max_lat),
            "west": min(min_lon, max_lon),
            "east": max(min_lon, max_lon),
        }

    def longest_edge_angle_deg(self) -> float:
        """Calculate the orientation angle (degrees) of the longest edge."""
        exterior_coords = list(self.poly_m.exterior.coords)
        max_len = -1.0
        best_angle = 0.0
        for i in range(len(exterior_coords) - 1):
            p1, p2 = exterior_coords[i], exterior_coords[i + 1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.hypot(dx, dy)
            if length > max_len:
                max_len = length
                best_angle = math.degrees(math.atan2(dy, dx)) % 180.0
        return best_angle

    def generate_crop_rows(
        self, spacing_m: float = 0.75, angle_deg: float = 0.0
    ) -> List[List[Tuple[float, float]]]:
        """Generate illustrative crop-row lines clipped to the field polygon."""
        if spacing_m <= 0.1:
            spacing_m = 0.75

        # Rotate polygon so rows are horizontal in rotated frame
        origin = self.poly_m.centroid
        rotated_poly = rotate(self.poly_m, -angle_deg, origin=origin)
        minx, miny, maxx, maxy = rotated_poly.bounds

        lines = []
        curr_y = miny + (spacing_m / 2.0)
        while curr_y < maxy:
            test_line = LineString([(minx - 10.0, curr_y), (maxx + 10.0, curr_y)])
            clipped = rotated_poly.intersection(test_line)
            if not clipped.is_empty:
                if clipped.geom_type == "LineString":
                    lines.append(clipped)
                elif clipped.geom_type == "MultiLineString":
                    lines.extend(list(clipped.geoms))
            curr_y += spacing_m

        # Rotate lines back to UTM, then convert to lat/lon
        latlon_rows: List[List[Tuple[float, float]]] = []
        for line in lines:
            unrotated = rotate(line, angle_deg, origin=origin)
            coords_m = list(unrotated.coords)
            pts = []
            for xm, ym in coords_m:
                lon, lat = self.proj.inverse(xm, ym)
                pts.append((round(lat, 7), round(lon, 7)))
            if len(pts) >= 2:
                latlon_rows.append(pts)
        return latlon_rows
