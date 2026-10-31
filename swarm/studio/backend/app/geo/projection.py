"""Auto UTM local metric projection utilities."""

from __future__ import annotations

import math
from typing import List, Tuple
from pyproj import Transformer


def get_utm_epsg(lat: float, lon: float) -> int:
    """Calculate the WGS84 UTM EPSG code for a latitude and longitude."""
    zone = int((lon + 180.0) / 6.0) + 1
    zone = min(max(zone, 1), 60)
    if lat >= 0:
        return 32600 + zone
    else:
        return 32700 + zone


class LocalProjection:
    """Handles projection between WGS84 (lat/lon) and local metric UTM."""

    def __init__(self, ref_lat: float, ref_lon: float):
        self.ref_lat = ref_lat
        self.ref_lon = ref_lon
        self.epsg = get_utm_epsg(ref_lat, ref_lon)
        self._to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{self.epsg}", always_xy=True)
        self._to_latlon = Transformer.from_crs(f"EPSG:{self.epsg}", "EPSG:4326", always_xy=True)

    def forward(self, lon: float, lat: float) -> Tuple[float, float]:
        """Project (lon, lat) in degrees to (x, y) in metres."""
        x, y = self._to_utm.transform(lon, lat)
        return float(x), float(y)

    def inverse(self, x: float, y: float) -> Tuple[float, float]:
        """Unproject (x, y) in metres to (lon, lat) in degrees."""
        lon, lat = self._to_latlon.transform(x, y)
        return float(lon), float(lat)

    def forward_poly(self, coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Project a list of (lat, lon) coordinates to metric (x, y)."""
        return [self.forward(lon, lat) for lat, lon in coords]

    def inverse_poly(self, coords_m: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Convert a list of metric (x, y) coordinates back to (lat, lon)."""
        res = []
        for x, y in coords_m:
            lon, lat = self.inverse(x, y)
            res.append((round(lat, 7), round(lon, 7)))
        return res
