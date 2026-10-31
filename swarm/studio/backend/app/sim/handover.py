"""Low-battery handover decision logic and backup drone activation."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.planning.path import Waypoint
from app.planning.stage2 import DecisionRecord, CandidateEvaluation


def evaluate_handover_candidates(
    unfinished_waypoints: List[Waypoint],
    active_drones: List[Dict[str, Any]],
    backup_drones: List[Dict[str, Any]],
    base_x: float,
    base_y: float,
    sim_time: float,
    low_drone_id: int,
) -> Tuple[Optional[int], str, DecisionRecord]:
    """Evaluate candidate drones for taking over unfinished workload."""
    first_wp = unfinished_waypoints[0]
    target_x, target_y = first_wp.x_m, first_wp.y_m

    candidates: List[CandidateEvaluation] = []

    # Priority 1: Backup drones standing by at base
    for b in backup_drones:
        d_id = b["drone_id"]
        dist = math.hypot(target_x - base_x, target_y - base_y)
        batt_pct = b["battery_sim"].battery_pct
        feasible = batt_pct >= 50.0  # Fresh backup
        score = 1000.0 - dist if feasible else -1.0

        candidates.append(
            CandidateEvaluation(
                cluster_id=f"Drone-{d_id} (Backup)",
                distance_m=round(dist, 1),
                energy_Wh=0.0,
                priority=100.0,
                score=round(score, 1),
                feasible=feasible,
            )
        )

    # Priority 2: Operational active drones in the air
    for a in active_drones:
        d_id = a["drone_id"]
        if d_id == low_drone_id or a["state"] in ("RTH", "LANDED"):
            continue

        curr_x, curr_y = a["x_m"], a["y_m"]
        dist = math.hypot(target_x - curr_x, target_y - curr_y)
        can_take = a["battery_sim"].can_continue(curr_x, curr_y, base_x, base_y, alt_m=20.0)
        score = (500.0 - dist) if can_take else -1.0

        candidates.append(
            CandidateEvaluation(
                cluster_id=f"Drone-{d_id} (Active)",
                distance_m=round(dist, 1),
                energy_Wh=0.0,
                priority=50.0,
                score=round(score, 1),
                feasible=can_take,
            )
        )

    # Sort candidates by score descending
    candidates.sort(key=lambda c: c.score, reverse=True)

    chosen_drone_id: Optional[int] = None
    reason = ""

    # Check if backup drone is available
    available_backups = [b for b in backup_drones if b["state"] == "STANDBY" and b["battery_sim"].battery_pct >= 50.0]
    if available_backups:
        chosen = available_backups[0]
        chosen_drone_id = chosen["drone_id"]
        reason = f"Backup Drone {chosen_drone_id} launched from Base to take over {len(unfinished_waypoints)} cells at handover node."
    else:
        # Check active drones
        feasible_active = [c for c in candidates if c.feasible and "Active" in c.cluster_id]
        if feasible_active:
            # Extract id
            cand_str = feasible_active[0].cluster_id
            chosen_drone_id = int(cand_str.split()[0].replace("Drone-", ""))
            reason = f"Active Drone {chosen_drone_id} reassigned to take over {len(unfinished_waypoints)} cells by proximity score."
        else:
            reason = f"No backup or feasible active drone available. {len(unfinished_waypoints)} cells marked uncovered."

    dec_record = DecisionRecord(
        t=round(sim_time, 1),
        drone_id=low_drone_id,
        rule="LOW_BATTERY_HANDOVER_DISPATCH",
        candidates=candidates,
        chosen_cluster_id=f"Drone-{chosen_drone_id}" if chosen_drone_id else "NONE",
        reason=reason,
    )

    return chosen_drone_id, reason, dec_record
