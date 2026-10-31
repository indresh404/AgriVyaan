# AgriVyaan Swarm Algorithms Specification

> **Notice:** Simulation only — synthetic zones and an abstract energy model. Not real crop detections, not real flight or battery results.

This document outlines the allocation and fault-recovery algorithms implemented in `agrivyaan_swarm`.

---

## 1. Baseline: Greedy Nearest-Task Allocator

### 1.1 Trigger Timing
An allocation round executes deterministically at:
1. $t = 0$ (Mission start).
2. Whenever any drone transitions to `IDLE` (e.g. finishes inspection).
3. Whenever tasks are released back to `PENDING` due to fault detection.

### 1.2 Procedure
1. **Identify Eligible Drones:** Drones that are alive (`status != FAILED`), have working communications (`comm_lost == False`), and are currently `IDLE` or `COMPLETED` at base.
2. **Order Drones:** Sort eligible drones in ascending order of `drone.id`.
   > **Known Bias Note:** Sequential drone ordering introduces a mild first-drone advantage where Drone 0 gets first pick of closest tasks.
3. **Task Evaluation:** For each eligible drone:
   - Filter `PENDING` tasks for energy feasibility under conservative safety margin:
     $$E_{\text{avail}} = E - \text{reserve} \ge \text{safety\_factor} \times \text{travel}(p \to k) + \text{inspect}_k + \text{safety\_factor} \times \text{travel}(k \to \text{base})$$
   - Sort feasible candidate tasks by Euclidean distance:
     $$\text{dist} = \sqrt{(x_d - x_k)^2 + (y_d - y_k)^2}$$
   - Tie-breaking: In case of identical distance, select the task with the lowest `task.id`.
4. **Immediate Assignment:** The selected task is immediately marked `ASSIGNED` and bound to the drone. This guarantees that no task can be assigned twice.
5. **Base Return:** Drones with no feasible tasks are commanded to return to base (`RETURNING`), landing into `COMPLETED`.

---

## 2. Fault Tolerance and Recovery Policies

### 2.1 Hard Failure (`HARD_FAILURE`)
- **Trigger:** Configured via elapsed simulation time $t$ or completed task threshold.
- **Drone Action:** Drone immediately halts in place (`status = FAILED`), disabled from further flight.
- **Coordinator Action:** After a configurable `detection_delay_s`, the central coordinator acknowledges the failure:
  1. Any `ASSIGNED` or `IN_PROGRESS` tasks assigned to this drone are released.
  2. For released tasks, `attempts` is incremented by 1 (partial inspection is lost).
  3. If $\text{attempts} \ge \text{max\_attempts}$ (default 3), the task is marked `UNREACHABLE`.
  4. Otherwise, task returns to `PENDING`.
  5. An allocation round triggers immediately to allow operational drones to take over.
  6. Completed tasks are preserved.

### 2.2 Communication Loss (`COMM_LOSS`)
- **Model Assumption:** The drone executes flight plans autonomously onboard and never depends on the laptop to fly safely.
- **Behavior:**
  1. The drone finishes its current assigned task autonomously.
  2. Upon completing the inspection, it immediately commands an autonomous return to base.
  3. Upon landing, its data is recovered, but it remains unavailable for further missions (`comm_lost = True`).

### 2.3 Unreachable Task Classification
At mission conclusion:
- A remaining `PENDING` task is classified as `UNREACHABLE` if it is energy-infeasible from base for **all** surviving operational drones.
- If **no** surviving operational drones exist, leftover tasks remain `PENDING` and the run reports `ALL_DRONES_FAILED` or `INCOMPLETE_UNFINISHED_TASKS`.

---

## 3. Future Algorithms (Roadmap / Not in v1)

| Algorithm | Status | Purpose |
| :--- | :--- | :--- |
| **Priority-Gain Allocator** | Extension point | Weighs distance against $\text{priority} \times \text{gain} / \text{energy}$. |
| **CBBA (Consensus-Based Bundle Algorithm)** | Planned | Distributed multi-task auction without central coordinator. |
| **DBSCAN Spatial Clustering** | Planned | Groups nearby anomaly clusters before assigning inspection tours. |
