"""Stitching satellite tiles into project field orthomosaics and thumbnails."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
from PIL import Image

from app.imagery.tiles import (
    deg2num,
    num2deg,
    get_tiles_for_bounds,
    fetch_tile,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STUDIO_DIR = BACKEND_DIR.parent
PROJECTS_DATA_DIR = STUDIO_DIR / "data" / "projects"


def build_field_mosaic(
    project_id: str,
    south: float,
    north: float,
    west: float,
    east: float,
    zoom: int = 18,
) -> Dict[str, Any]:
    """Stitch satellite tiles into a single georeferenced orthomosaic image for the field."""
    proj_dir = PROJECTS_DATA_DIR / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    tiles = get_tiles_for_bounds(south, north, west, east, zoom=zoom)
    if not tiles:
        raise ValueError("No tiles calculated for given bounding box.")

    z = tiles[0][0]
    xs = [t[1] for t in tiles]
    ys = [t[2] for t in tiles]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    cols = x_max - x_min + 1
    rows = y_max - y_min + 1

    mosaic_w = cols * 256
    mosaic_h = rows * 256

    mosaic_img = Image.new("RGB", (mosaic_w, mosaic_h))

    for z_tile, xtile, ytile in tiles:
        tile_img = fetch_tile(z_tile, xtile, ytile)
        pos_x = (xtile - x_min) * 256
        pos_y = (ytile - y_min) * 256
        mosaic_img.paste(tile_img, (pos_x, pos_y))

    # Calculate exact georeferenced corners of the mosaic canvas
    top_lat, left_lon = num2deg(x_min, y_min, z)
    bottom_lat, right_lon = num2deg(x_max + 1, y_max + 1, z)

    mosaic_path = proj_dir / "mosaic.jpg"
    thumb_path = proj_dir / "mosaic_thumb.jpg"

    mosaic_img.save(mosaic_path, "JPEG", quality=85)

    # Generate thumbnail
    thumb = mosaic_img.copy()
    thumb.thumbnail((360, 360), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80)

    return {
        "project_id": project_id,
        "zoom": z,
        "pixel_w": mosaic_w,
        "pixel_h": mosaic_h,
        "mosaic_path": str(mosaic_path),
        "thumb_path": str(thumb_path),
        "bounds": {
            "north": top_lat,
            "south": bottom_lat,
            "west": left_lon,
            "east": right_lon,
        },
    }
