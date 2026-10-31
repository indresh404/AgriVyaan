"""Camera optical footprint and ground sampling distance (GSD) calculations."""

from __future__ import annotations

from typing import Dict
from pydantic import BaseModel, Field


class CameraPreset(BaseModel):
    name: str = "Pi Camera HQ (6mm Lens)"
    sensor_w_mm: float = 6.287
    sensor_h_mm: float = 4.712
    focal_length_mm: float = 6.0
    image_w_px: int = 4056
    image_h_px: int = 3040


class CameraFootprintResult(BaseModel):
    altitude_m: float
    footprint_w_m: float
    footprint_h_m: float
    gsd_mm_per_px: float
    coverage_area_per_shot_m2: float


def calculate_footprint(
    altitude_m: float,
    sensor_w_mm: float = 6.287,
    sensor_h_mm: float = 4.712,
    focal_length_mm: float = 6.0,
    image_w_px: int = 4056,
    image_h_px: int = 3040,
) -> CameraFootprintResult:
    """Calculate camera footprint width, height, and GSD at a given altitude.

    Formulas from Section 6.2:
      Fw = alt * sensor_w / focal
      Fh = alt * sensor_h / focal
      GSD (mm/px) = sensor_w * (alt * 1000) / (focal * image_w_px)
    """
    if focal_length_mm <= 0:
        raise ValueError("Focal length must be positive.")
    if altitude_m <= 0:
        raise ValueError("Altitude must be positive.")

    fw = altitude_m * (sensor_w_mm / focal_length_mm)
    fh = altitude_m * (sensor_h_mm / focal_length_mm)
    alt_mm = altitude_m * 1000.0
    gsd = (sensor_w_mm * alt_mm) / (focal_length_mm * image_w_px)

    return CameraFootprintResult(
        altitude_m=round(altitude_m, 2),
        footprint_w_m=round(fw, 3),
        footprint_h_m=round(fh, 3),
        gsd_mm_per_px=round(gsd, 3),
        coverage_area_per_shot_m2=round(fw * fh, 2),
    )
