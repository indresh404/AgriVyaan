# AgriVyaan Swarm Architecture & Data Flow

> **Notice:** Simulation only — synthetic zones and an abstract energy model. Not real crop detections, not real flight or battery results.

This document describes the architectural layering, data flow, and separation boundaries of the `agrivyaan_swarm` package.

---

## 1. High-Level Data Flow

```text
Scenario (Generator or JSON)
        │
        ▼
SimulationEngine ── uses ──► Allocator (Greedy)  +  FailureModel  +  DroneBackend (SimBackend)
        │
        ▼
RunRecording  (frames + events + metrics + config + seed)
        │
        ├──► Files: recording.json, metrics.json, metrics.csv, events.csv
        ├──► Matplotlib Static Plot (summary_plot.png)
        └──► Streamlit Replay & Comparison Dashboard
```

---

## 2. Hard Separation Rules

To prevent code entanglement and ensure robust testing:
1. **Engine Independence:** The simulation engine (`agrivyaan_swarm.simulation.engine`) never imports Matplotlib, Plotly, or Streamlit. It runs headlessly in pure Python.
2. **Dashboard Purity:** The dashboard contains zero physics or allocation logic. It exclusively consumes `RunRecording` artifacts or calls the high-level `run_simulation(config)` API.
3. **Pure Figure Builders:** Figure-generating functions (`agrivyaan_swarm.dashboard.figures`) are pure: `RunRecording + frame_index -> go.Figure`.
4. **Backend Abstraction:** Actuation is decoupled through the `DroneBackend` interface (`get_position()`, `goto(x, y)`, `start_inspection()`, `step(dt)`). In v1, `SimBackend` implements virtual kinematics; in future versions, a `MavlinkBackend` can be plugged in without changing the allocation or coordination layers.

---

## 3. Module Hierarchy

```text
src/agrivyaan_swarm/
├── models/             # Domain entities (Drone, Task, Field, RunRecording)
├── environment/        # Geometry, WGS84 projection, synthetic task generator
├── backends/           # DroneBackend interface and SimBackend virtual physics
├── allocation/         # Allocator base, GreedyAllocator, reassignment logic
├── simulation/         # Kinematics, abstract battery model, failure manager, engine
├── metrics/            # Invariant validation, statistical calculations, and CSV/JSON exporters
├── visualization/      # Matplotlib Agg static figures and animations
└── dashboard/          # Streamlit user interface, views, and Plotly figure builders
```

---

## 4. RunRecording Lifecycle

1. **Initialization:** Engine generates world snapshot at $t = 0$.
2. **Stepping:** Kinematics advance in fixed intervals $dt = 0.5\text{s}$.
3. **Sampling:** A frame is captured every `record_every_n_steps` (default 4 steps = 2.0s intervals) ensuring memory-efficient replays (< 300 frames per run).
4. **Finalization:** Invariants checked, metrics aggregated, and recording serialized to `data/results/<run_id>/recording.json`.
