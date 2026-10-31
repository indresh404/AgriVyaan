"""Geographic coordinate transformations between local metres and WGS84 lat/lon."""

from __future__ import annotations

import math
from typing import Tuple

METRES_PER_DEGREE_LAT = 111320.0


def local_to_wgs84(
    x_m: float,
    y_m: float,
    origin_lat: float,
    origin_lon: float,
) -> Tuple[float, float]:
    """Convert local (x, y) coordinates in metres to WGS84 (lat, lon) degrees.

    x_m: Easting in metres from origin
    y_m: Northing in metres from origin
    origin_lat, origin_lon: Origin in degrees WGS84
    """
    lat_rad = math.radians(origin_lat)
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) < 1e-12:
        raise ValueError("Latitude too close to pole for planar projection.")

    dlat = y_m / METRES_PER_DEGREE_LAT
    dlon = x_m / (METRES_PER_DEGREE_LAT * cos_lat)

    return (origin_lat + dlat, origin_lon + dlon)


def wgs84_to_local(
    lat: float,
    lon: float,
    origin_lat: float,
    origin_lon: float,
) -> Tuple[float, float]:
    """Convert WGS84 (lat, lon) degrees to local (x, y) coordinates in metres.

    origin_lat, origin_lon: Reference origin in degrees WGS84
    """
    lat_rad = math.radians(origin_lat)
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) < 1e-12:
        raise ValueError("Latitude too close to pole for planar projection.")

    dlat = lat - origin_lat
    dlon = lon - origin_lon

    y_m = dlat * METRES_PER_DEGREE_LAT
    x_m = dlon * (METRES_PER_DEGREE_LAT * cos_lat)

    return (x_m, y_m)
