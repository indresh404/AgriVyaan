"""Handling custom user orthophoto image uploads with bounds."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Tuple
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STUDIO_DIR = BACKEND_DIR.parent
PROJECTS_DATA_DIR = STUDIO_DIR / "data" / "projects"


def save_user_orthophoto(
    project_id: str,
    src_file_path: Path,
    north: float,
    south: float,
    west: float,
    east: float,
) -> Dict[str, Any]:
    """Store uploaded user orthophoto and set project mosaic metadata."""
    proj_dir = PROJECTS_DATA_DIR / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    dest_mosaic = proj_dir / "mosaic.jpg"
    thumb_path = proj_dir / "mosaic_thumb.jpg"

    img = Image.open(src_file_path).convert("RGB")
    img.save(dest_mosaic, "JPEG", quality=88)

    thumb = img.copy()
    thumb.thumbnail((360, 360), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80)

    w, h = img.size
    return {
        "project_id": project_id,
        "pixel_w": w,
        "pixel_h": h,
        "mosaic_path": str(dest_mosaic),
        "thumb_path": str(thumb_path),
        "bounds": {
            "north": north,
            "south": south,
            "west": west,
            "east": east,
        },
        "source": "user_upload",
    }
