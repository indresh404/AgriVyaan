"""Stage-2 Targeted Micro-Inspection clustering and greedy assignment."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from shapely.geometry import Point, MultiPoint, Polygon, box
from shapely.ops import unary_union

from app.camera.footprint import calculate_footprint
from app.geo.projection import LocalProjection
from app.planning.path import Waypoint


class HotspotMark(BaseModel):
    id: str
    lat: float
    lon: float
    type: str  # "late_blight", "early_blight", "aphid", "water_stress", "nutrient", "other"
    severity: float = 0.8
    note: str = ""
    revealed: bool = False
    revealed_at_s: Optional[float] = None


class HotspotCluster(BaseModel):
    cluster_id: str
    hotspot_ids: List[str]
    center_lat: float
    center_lon: float
    center_x_m: float
    center_y_m: float
    severity_max: float
    area_m2: float
    priority_score: float  # severity * area
    subgrid_waypoints: List[Waypoint] = []
    assigned_drone_id: Optional[int] = None


class CandidateEvaluation(BaseModel):
    cluster_id: str
    distance_m: float
    energy_Wh: float
    priority: float
    score: float
    feasible: bool


class DecisionRecord(BaseModel):
    t: float
    drone_id: int
    rule: str
    candidates: List[CandidateEvaluation]
    chosen_cluster_id: Optional[str]
    reason: str


def cluster_hotspots(
    hotspots: List[HotspotMark],
    proj: LocalProjection,
    distance_threshold_m: float = 25.0,
    stage2_alt_m: float = 8.0,
) -> List[HotspotCluster]:
    """Group nearby hotspots into clusters using metric distance threshold."""
    if not hotspots:
        return []

    # Map hotspots to local metric coords
    metric_pts = []
    for h in hotspots:
        x, y = proj.forward(h.lon, h.lat)
        metric_pts.append((h, x, y))

    # Connected components graph clustering
    n = len(metric_pts)
    adj = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            dist = math.hypot(metric_pts[i][1] - metric_pts[j][1], metric_pts[i][2] - metric_pts[j][2])
            if dist <= distance_threshold_m:
                adj[i].append(j)
                adj[j].append(i)

    visited = set()
    clusters: List[HotspotCluster] = []
    cluster_num = 1

    # Stage-2 fine sub-grid footprint at A2
    fp2 = calculate_footprint(stage2_alt_m)
    subcell_side = max(min(fp2.footprint_w_m, fp2.footprint_h_m) * 0.8, 1.5)

    for i in range(n):
        if i in visited:
            continue
        comp = []
        queue = [i]
        visited.add(i)
        while queue:
            curr = queue.pop(0)
            comp.append(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Build cluster representation
        comp_members = [metric_pts[idx] for idx in comp]
        h_ids = [m[0].id for m in comp_members]
        avg_x = sum(m[1] for m in comp_members) / len(comp_members)
        avg_y = sum(m[2] for m in comp_members) / len(comp_members)
        max_sev = max(m[0].severity for m in comp_members)
        c_lon, c_lat = proj.inverse(avg_x, avg_y)

        # Cluster bounding geometry
        if len(comp_members) == 1:
            cluster_area = math.pi * (10.0**2)  # 10m radius default inspection zone
        else:
            pts_geom = MultiPoint([(m[1], m[2]) for m in comp_members])
            hull = pts_geom.convex_hull.buffer(12.0)
            cluster_area = hull.area

        prio = round(max_sev * cluster_area, 2)

        # Generate fine sub-grid inspection waypoints at A2
        sub_waypoints: List[Waypoint] = []
        wp_idx = 0
        for m in comp_members:
            h_obj, hx, hy = m
            hlon, hlat = proj.inverse(hx, hy)
            sub_waypoints.append(
                Waypoint(
                    index=wp_idx,
                    cell_id=f"S2-{h_obj.id}",
                    lat=round(hlat, 7),
                    lon=round(hlon, 7),
                    x_m=round(hx, 2),
                    y_m=round(hy, 2),
                    altitude_m=stage2_alt_m,
                    action="CAPTURE",
                )
            )
            wp_idx += 1

        clusters.append(
            HotspotCluster(
                cluster_id=f"CLUSTER-{cluster_num:02d}",
                hotspot_ids=h_ids,
                center_lat=round(c_lat, 7),
                center_lon=round(c_lon, 7),
                center_x_m=round(avg_x, 2),
                center_y_m=round(avg_y, 2),
                severity_max=round(max_sev, 2),
                area_m2=round(cluster_area, 1),
                priority_score=prio,
                subgrid_waypoints=sub_waypoints,
            )
        )
        cluster_num += 1

    # Sort clusters descending by priority (severity * area)
    clusters.sort(key=lambda c: c.priority_score, reverse=True)
    return clusters
