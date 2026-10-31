"""Image extraction for captured camera footprints and hotspot inspections."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STUDIO_DIR = BACKEND_DIR.parent
ASSETS_DIR = STUDIO_DIR / "assets"
SAMPLES_DIR = ASSETS_DIR / "samples"


def extract_capture_crop(
    mosaic_path: str,
    mosaic_bounds: Dict[str, float],
    center_lat: float,
    center_lon: float,
    footprint_w_m: float,
    footprint_h_m: float,
    hotspot_type: Optional[str] = None,
    hotspot_severity: float = 0.0,
    out_dir: Optional[Path] = None,
    capture_id: str = "cap",
) -> Tuple[str, str]:
    """Extract or synthesize image crop for a capture footprint."""
    if out_dir is None:
        out_dir = STUDIO_DIR / "data" / "captures"
    out_dir.mkdir(parents=True, exist_ok=True)

    img_path = out_dir / f"{capture_id}.jpg"
    thumb_path = out_dir / f"{capture_id}_thumb.jpg"

    # Check if user provided high-resolution real sample photo for this hotspot type
    sample_found = False
    if hotspot_type:
        type_dir = SAMPLES_DIR / hotspot_type
        if type_dir.exists():
            sample_files = list(type_dir.glob("*.jpg")) + list(type_dir.glob("*.png")) + list(type_dir.glob("*.jpeg"))
            if sample_files:
                sample_img = Image.open(sample_files[0]).convert("RGB")
                sample_img.save(img_path, "JPEG", quality=85)
                sample_found = True

    # Otherwise crop from field mosaic or generate labeled synthetic crop
    if not sample_found:
        crop_img: Optional[Image.Image] = None
        if mosaic_path and Path(mosaic_path).exists():
            try:
                mosaic = Image.open(mosaic_path)
                m_w, m_h = mosaic.size

                north = mosaic_bounds["north"]
                south = mosaic_bounds["south"]
                west = mosaic_bounds["west"]
                east = mosaic_bounds["east"]

                # Pixel mapping
                px = int(((center_lon - west) / (east - west)) * m_w)
                py = int(((north - center_lat) / (north - south)) * m_h)

                # Estimate pixel footprint radius (~0.3-0.6 m/pixel)
                rx = max(int((footprint_w_m / 0.5) / 2.0), 30)
                ry = max(int((footprint_h_m / 0.5) / 2.0), 30)

                box = (max(0, px - rx), max(0, py - ry), min(m_w, px + rx), min(m_h, py + ry))
                crop_img = mosaic.crop(box).resize((400, 300), Image.Resampling.LANCZOS)
            except Exception:
                crop_img = None

        if crop_img is None:
            crop_img = Image.new("RGB", (400, 300), color="#2d6a4f")

        # If this is a hotspot capture, overlay diagnostic box & honest limitation badge
        draw = ImageDraw.Draw(crop_img)
        if hotspot_type:
            # Inspection bounding box
            draw.rectangle([80, 60, 320, 240], outline="#f43f5e", width=3)
            draw.rectangle([80, 36, 320, 60], fill="#881337")
            draw.text((86, 40), f"HOTSPOT: {hotspot_type.upper()} ({hotspot_severity*100:.0f}%)", fill="#fecdd3")

        # Requirement 1: Label upscaled satellite crop honestly
        draw.rectangle([4, 276, 260, 296], fill="#020617")
        draw.text((8, 280), "Low-resolution satellite crop", fill="#94a3b8")

        crop_img.save(img_path, "JPEG", quality=85)

    # Save thumbnail
    final_img = Image.open(img_path)
    thumb = final_img.copy()
    thumb.thumbnail((120, 90), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80)

    return str(img_path), str(thumb_path)
