# AgriVyaan Swarm Roadmap & Implementation Status

> **Notice:** Simulation only — synthetic zones and an abstract energy model. Not real crop detections, not real flight or battery results.

This document clearly distinguishes what has been implemented and tested from planned future work and out-of-scope hardware capabilities.

---

## 1. Implemented & Tested (v1.0)

- [x] **Core Multi-Agent Simulation Engine:** Deterministic kinematic propagation, time stepping ($dt = 0.5\text{s}$), overshoot clamping.
- [x] **Abstract Battery Model:** Distance and inspection duration energy burn, return reserve thresholds, feasibility checks with configurable safety factors.
- [x] **Greedy Allocation Baseline:** Nearest-feasible assignment with sequential ID tie-breaking and immediate assignment locks.
- [x] **Failure Modes & Resilience:** Injected `HARD_FAILURE` (mid-flight stop + task release after detection delay) and `COMM_LOSS` (autonomous task completion + return to base).
- [x] **Invariant Verification:** Automated runtime assertion of 0 duplicate assignments and 0 battery reserve violations.
- [x] **Artifact Serialization:** Full `RunRecording` with frames, events, and metrics written to JSON and CSV.
- [x] **Streamlit + Plotly Dashboard:** Mission replay with single timeline slider, live telemetry, event filters, metrics cards, and scenario table editor.
- [x] **Multi-Drone Comparison:** Paired comparison experiments across 1, 2, and 3 drones under nominal, energy-constrained, and failure settings.
- [x] **Comprehensive Automated Test Suite:** 27 unit, integration, and UI smoke tests via pytest.

---

## 2. Planned (Future Software Iterations)

- [ ] **Priority-Gain Allocator:** Optimization heuristic weighing $(\text{priority} \times \text{gain}) / \text{energy\_cost}$.
- [ ] **Spatial Clustering (DBSCAN):** Pre-clustering proximate crop anomalies using `scikit-learn` before tour allocation.
- [ ] **Distributed Consensus (CBBA):** Consensus-Based Bundle Algorithm for decentralized task auctioning without a single point of failure.
- [ ] **Dynamic Recharging:** Drone battery recharge stations and multi-sortie mission schedules.

---

## 3. Unvalidated / Out of Scope (Requires Physical Hardware & Live Systems)

- [ ] **MAVLink / ArduPilot SITL Integration:** Hardware-in-the-loop and software-in-the-loop simulation via `pymavlink`. (Will plug in via `DroneBackend` interface; not implemented in v1).
- [ ] **Collision Avoidance:** Inter-drone spatial deconfliction and geofencing.
- [ ] **Real Crop Detection:** Computer vision inference on live multispectral cameras. (All anomaly inputs in v1 are synthetic).
- [ ] **Calibrated Battery Chemistry:** Validation against real LiPo / Li-ion discharge curves and ambient wind conditions.
