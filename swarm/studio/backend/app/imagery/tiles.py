"""Satellite tile downloading, disk caching, and offline fallback."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import List, Optional, Tuple
import httpx
from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STUDIO_DIR = BACKEND_DIR.parent
CACHE_DIR = STUDIO_DIR / "data" / "cache" / "tiles"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "AgriVyaanMissionStudio/1.0 (Simulation Prototype; Research & Education)"

# Esri World Imagery endpoint
ESRI_TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    """Convert WGS84 lat/lon to slippy map tile coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)


def num2deg(xtile: int, ytile: int, zoom: int) -> Tuple[float, float]:
    """Convert slippy map tile coordinate to NW corner (lat, lon)."""
    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


def get_tile_cache_path(zoom: int, x: int, y: int) -> Path:
    """Return local disk cache file path for tile."""
    z_dir = CACHE_DIR / str(zoom) / str(x)
    z_dir.mkdir(parents=True, exist_ok=True)
    return z_dir / f"{y}.jpg"


def generate_synthetic_tile(zoom: int, x: int, y: int) -> Image.Image:
    """Generate high-contrast synthetic agricultural crop texture for offline simulation."""
    img = Image.new("RGB", (256, 256), color="#1b4332")
    draw = ImageDraw.Draw(img)

    # Draw organic agricultural crop rows
    for row_y in range(0, 256, 12):
        row_color = "#2d6a4f" if (row_y // 12) % 2 == 0 else "#40916c"
        draw.rectangle([0, row_y, 256, row_y + 8], fill=row_color)

    # Subtle soil borders and coordinates
    draw.rectangle([0, 0, 255, 255], outline="#081c15", width=1)
    return img


def fetch_tile(zoom: int, x: int, y: int, timeout_s: float = 3.0) -> Image.Image:
    """Fetch tile from disk cache, network, or offline synthetic fallback."""
    cache_path = get_tile_cache_path(zoom, x, y)
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGB")
        except Exception:
            pass

    # Try downloading from Esri
    url = ESRI_TILE_URL.format(z=zoom, x=x, y=y)
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                return Image.open(cache_path).convert("RGB")
    except Exception:
        pass

    # Offline fallback
    synth = generate_synthetic_tile(zoom, x, y)
    try:
        synth.save(cache_path, "JPEG")
    except Exception:
        pass
    return synth


def get_tiles_for_bounds(
    south: float, north: float, west: float, east: float, zoom: int = 18, max_tiles: int = 300
) -> List[Tuple[int, int, int]]:
    """Calculate list of tile (z, x, y) covering bounding box up to max_tiles cap."""
    x0, y1 = deg2num(north, west, zoom)
    x1, y0 = deg2num(south, east, zoom)

    x_min, x_max = min(x0, x1), max(x0, x1)
    y_min, y_max = min(y0, y1), max(y0, y1)

    tile_count = (x_max - x_min + 1) * (y_max - y_min + 1)
    # If too many tiles at zoom, adjust zoom downward to fit under max_tiles cap
    while tile_count > max_tiles and zoom > 12:
        zoom -= 1
        x0, y1 = deg2num(north, west, zoom)
        x1, y0 = deg2num(south, east, zoom)
        x_min, x_max = min(x0, x1), max(x0, x1)
        y_min, y_max = min(y0, y1), max(y0, y1)
        tile_count = (x_max - x_min + 1) * (y_max - y_min + 1)

    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((zoom, x, y))
    return tiles
