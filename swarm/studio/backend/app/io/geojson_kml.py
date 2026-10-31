"""Import and export handlers for GeoJSON and KML field polygon files."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple


def parse_geojson_polygon(geojson_text: str) -> List[Tuple[float, float]]:
    """Parse GeoJSON string and extract list of (lat, lon) coordinates."""
    data = json.loads(geojson_text)

    # Handle FeatureCollection
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("GeoJSON FeatureCollection contains no features.")
        geom = features[0].get("geometry", {})
    elif data.get("type") == "Feature":
        geom = data.get("geometry", {})
    else:
        geom = data

    geom_type = geom.get("type")
    coords = geom.get("coordinates", [])

    if geom_type == "Polygon":
        # GeoJSON is [lon, lat]
        ring = coords[0]
        return [(round(float(pt[1]), 7), round(float(pt[0]), 7)) for pt in ring]
    elif geom_type == "MultiPolygon":
        ring = coords[0][0]
        return [(round(float(pt[1]), 7), round(float(pt[0]), 7)) for pt in ring]
    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}. Expected Polygon.")


def parse_kml_polygon(kml_text: str) -> List[Tuple[float, float]]:
    """Parse KML string and extract list of (lat, lon) coordinates from <coordinates> tag."""
    # Strip XML namespace if present
    root = ET.fromstring(kml_text)
    coord_elems = root.findall(".//{*}coordinates")
    if not coord_elems:
        coord_elems = root.findall(".//coordinates")
    if not coord_elems:
        raise ValueError("No <coordinates> tag found in KML content.")

    raw_text = coord_elems[0].text.strip()
    pts: List[Tuple[float, float]] = []
    # Format: lon,lat,alt lon,lat,alt ...
    for token in raw_text.split():
        parts = token.split(",")
        if len(parts) >= 2:
            lon = float(parts[0].strip())
            lat = float(parts[1].strip())
            pts.append((round(lat, 7), round(lon, 7)))

    if len(pts) < 3:
        raise ValueError("KML must contain at least 3 polygon coordinates.")
    return pts


def polygon_to_geojson(latlon_coords: List[Tuple[float, float]]) -> Dict[str, Any]:
    """Convert list of (lat, lon) coordinates to standard GeoJSON Polygon."""
    # Close ring if not closed
    ring = [[lon, lat] for lat, lon in latlon_coords]
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
        "properties": {},
    }
