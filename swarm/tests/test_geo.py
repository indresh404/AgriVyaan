"""Tests for geographic transformations."""

import pytest
from agrivyaan_swarm.environment.geo import local_to_wgs84, wgs84_to_local


def test_geo_round_trip():
    """Verify conversion from local metres to WGS84 and back within 1mm tolerance."""
    origin_lat = 18.5204
    origin_lon = 73.8567

    test_points = [
        (0.0, 0.0),
        (50.0, 50.0),
        (-25.5, 100.2),
        (100.0, 200.0),
    ]

    for x_m, y_m in test_points:
        lat, lon = local_to_wgs84(x_m, y_m, origin_lat, origin_lon)
        x_rec, y_rec = wgs84_to_local(lat, lon, origin_lat, origin_lon)
        assert abs(x_rec - x_m) < 1e-3, f"X mismatch: {x_rec} vs {x_m}"
        assert abs(y_rec - y_m) < 1e-3, f"Y mismatch: {y_rec} vs {y_m}"


def test_geo_polar_exception():
    """Verify pole coordinate exception."""
    with pytest.raises(ValueError):
        local_to_wgs84(10.0, 10.0, 90.0, 0.0)
