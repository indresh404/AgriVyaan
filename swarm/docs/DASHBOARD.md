# AgriVyaan Swarm Dashboard Guide

> **Notice:** Simulation only — synthetic zones and an abstract energy model. Not real crop detections, not real flight or battery results.

The AgriVyaan dashboard provides an interactive, operator-focused graphical console built with **Streamlit** and **Plotly**.

---

## 1. Launching the Dashboard

```powershell
# From the swarm/ directory with virtualenv active:
streamlit run src/agrivyaan_swarm/dashboard/app.py
```

---

## 2. Interface Overview

### 2.1 Sidebar Controls
- **Scenario Source:**
  - *Generate Synthetic:* Adjust seed and task count on the fly.
  - *Load Scenario File:* Load pre-packaged test scenarios (e.g. `fixed_10.json`).
  - *Interactive Table Editor:* Directly edit $X, Y$ coordinates, durations, and priorities via an embedded spreadsheet table.
- **Fleet Parameters:** Slider for virtual drone fleet size (1 to 3) and battery capacity ($100$ to $1000\text{ EU}$).
- **Fault Injection:** Toggle to trigger `HARD_FAILURE` or `COMM_LOSS` on any drone with customizable trigger time and coordinator detection delay.
- **Geographic Reference:** Toggle local planar view vs WGS84 origin coordinates.
- **Action:** Click **Run Simulation** to execute.

---

## 3. Tabs Walkthrough

### Tab 1: Mission View
- **Single Unified Replay Slider:** Scrub through simulation time from start to finish.
- **Plotly Visualizer:** Displays field boundaries, base station, colored tasks (Green = Completed, Amber = Pending, Blue = Assigned, Purple = Inspecting, Red = Unreachable), drone positions, historical flight trails, and failure "X" markers.
- **Real-Time Telemetry Table:** Live drone state (position, remaining EU, current task).
- **Recent Events Feed:** Chronological event feed up to the replayed moment.

### Tab 2: Metrics & Export
- KPI cards for makespan, flight distance, energy spent, energy per completed task, and priority-weighted coverage.
- Invariant integrity verification status.
- One-click downloads for `metrics.json` and `metrics.csv`.

### Tab 3: Event Log
- Searchable and filterable table displaying every simulation event with timestamps, responsible drone, affected task, and narrative details.

### Tab 4: Fleet Scaling Compare
- Runs comparative benchmark across 1, 2, and 3 drones over multiple paired seeds.
- Plots makespan reduction alongside energy consumption trade-offs.

### Tab 5: Assumptions & Model
- Full documentation of mathematical energy equations, units, feasibility inequalities, and limitations.
