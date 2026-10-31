"""Asset loading and base64 encoding helpers for dashboard visual layers."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


def image_to_base64_data_uri(
    img_or_path: str | Path | Image.Image | bytes,
    mime_type: str = "image/png",
    max_dimension: Optional[int] = 1200,
) -> Optional[str]:
    """Safely convert a file path, PIL Image, or raw bytes into a base64 data URI string.

    Never raises an uncaught exception on invalid data; returns None and logs warning.
    """
    try:
        if isinstance(img_or_path, (str, Path)):
            path = Path(img_or_path)
            if not path.exists():
                return None
            img = Image.open(path)
            if path.suffix.lower() in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            else:
                mime_type = "image/png"
        elif isinstance(img_or_path, bytes):
            img = Image.open(io.BytesIO(img_or_path))
        elif isinstance(img_or_path, Image.Image):
            img = img_or_path
        else:
            return None

        # Optionally downsample large aerial imagery for fast Plotly rendering
        if max_dimension is not None:
            w, h = img.size
            if max(w, h) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        format_name = "PNG" if "png" in mime_type else "JPEG"
        if format_name == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffer, format=format_name, quality=90)
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"

    except Exception as e:
        logger.warning(f"Failed to encode image to base64: {e}")
        return None


def get_default_assets(assets_dir: str | Path = "assets") -> dict[str, Optional[str]]:
    """Load default farm and drone assets from assets/ directory if available."""
    p = Path(assets_dir)
    assets: dict[str, Optional[str]] = {
        "crop_image": None,
        "master_drone": None,
        "swarm_drone": None,
        "crop_early_blight": None,
        "crop_yellowish": None,
        "crop_growth": None,
    }

    if not p.exists():
        return assets

    # Farm background candidates (Crop imagery only - no satellite)
    if (p / "crop_image.png").exists():
        assets["crop_image"] = image_to_base64_data_uri(p / "crop_image.png")
    elif (p / "farm.png").exists():
        assets["crop_image"] = image_to_base64_data_uri(p / "farm.png")
    elif (p / "farm.jpg").exists():
        assets["crop_image"] = image_to_base64_data_uri(p / "farm.jpg")

    # Drone icons
    if (p / "master_drone.png").exists():
        assets["master_drone"] = image_to_base64_data_uri(p / "master_drone.png", max_dimension=256)

    if (p / "drone.png").exists():
        assets["swarm_drone"] = image_to_base64_data_uri(p / "drone.png", max_dimension=256)

    # Anomaly finding images
    if (p / "crop_early_blight.jpeg").exists():
        assets["crop_early_blight"] = image_to_base64_data_uri(p / "crop_early_blight.jpeg", max_dimension=600)
    if (p / "crop_yellowish.jpeg").exists():
        assets["crop_yellowish"] = image_to_base64_data_uri(p / "crop_yellowish.jpeg", max_dimension=600)
    if (p / "crop_growth.jpeg").exists():
        assets["crop_growth"] = image_to_base64_data_uri(p / "crop_growth.jpeg", max_dimension=600)

    return assets
