"""Synthetic spatial environmental field generator (Temperature & Relative Humidity)."""

from __future__ import annotations

import math
from typing import Tuple


class SyntheticEnvironment:
    """Generates smooth spatial-temporal synthetic temperature and humidity fields."""

    def __init__(
        self,
        base_temp_c: float = 24.5,
        base_rh_pct: float = 68.0,
        seed: int = 42,
    ):
        self.base_temp_c = base_temp_c
        self.base_rh_pct = base_rh_pct
        self.seed = seed

    def sample(
        self,
        lat: float,
        lon: float,
        t_seconds: float,
        dist_to_blight_m: float = 999.0,
    ) -> Tuple[float, float]:
        """Compute synthetic temperature (°C) and relative humidity (%) at (lat, lon, t)."""
        # Low-frequency spatial harmonics using coordinates and seed
        s = float(self.seed % 1000)
        u = (lon * 10000.0) + s
        v = (lat * 10000.0) + (s * 0.7)

        spatial_wave1 = math.sin(u * 0.05) * math.cos(v * 0.05)
        spatial_wave2 = math.cos(u * 0.02 + v * 0.03)
        spatial_var = (spatial_wave1 * 1.8) + (spatial_wave2 * 1.2)

        # Slow diurnal/time drift (~0.05°C per minute)
        time_drift = math.sin(t_seconds / 600.0) * 0.8

        temp = self.base_temp_c + spatial_var + time_drift

        # Humidity has inverse correlation to temperature
        rh_spatial = -spatial_var * 2.2 + math.cos(u * 0.04) * 3.0
        rh_drift = -time_drift * 1.5
        rh = self.base_rh_pct + rh_spatial + rh_drift

        # Section 6.10: Raise humidity near blight-type hotspots (microclimate)
        if dist_to_blight_m < 25.0:
            blight_boost = (25.0 - dist_to_blight_m) / 25.0 * 12.0
            rh += blight_boost
            temp -= blight_boost * 0.15

        # Clamp to realistic bounds
        temp = max(10.0, min(42.0, temp))
        rh = max(20.0, min(98.0, rh))

        return round(temp, 1), round(rh, 1)
