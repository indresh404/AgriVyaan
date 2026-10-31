# AgriVyaan Swarm Simulation & Replay Dashboard

> **⚠️ SIMULATION ONLY DISCLAIMER**  
> *This module is a software simulation only — featuring synthetic anomaly zones and an abstract energy model. It does not represent real multi-drone flight, physical coordination, real crop disease detection, or calibrated battery discharge curves. All performance improvements are computed directly from virtual simulation runs.*

---

## 1. Overview and Scope

AgriVyaan's precision agriculture workflow progresses through:  
`SCAN → ANOMALY → CLUSTER → PRIORITIZE → TARGETED RESCAN → EVIDENCE → VERIFY → ACT → RESCAN → OUTCOME`

The **`agrivyaan_swarm`** module simulates how a fleet of virtual drones can distribute the *targeted rescan* workload under battery constraints and recover when a drone experiences hardware failure or communications loss.

### Physical & Numerical Units (Fixed Everywhere)
- **Distance:** Metres ($\text{m}$). Standard field is $100\text{ m} \times 100\text{ m}$.
- **Time:** Seconds ($\text{s}$). Fixed simulation step $dt = 0.5\text{ s}$.
- **Speed:** Metres per second ($\text{m/s}$).
- **Energy:** Abstract Energy Units ($\text{EU}$). Not Watt-hours, not real battery percentage.

---

## 2. Quick Launch Options

All interfaces and simulation tools are consolidated inside this `swarm/` directory:

| Interface | Technology | Launch Command / Script | Description |
|---|---|---|---|
| **AgriVyaan Mission Studio** | FastAPI + React 18 / Vite / Leaflet | Double-click `run_studio.bat`<br>or `.\run_studio.ps1` | Full GIS satellite farm map, manual polygon & path planning, 60 FPS animated multi-drone simulation, low-battery handover, high-res capture inspection. |
| **Streamlit Dashboard** | Streamlit + Plotly | Double-click `run_dashboard.bat`<br>or `streamlit run src/agrivyaan_swarm/dashboard/app.py` | Multi-run simulation comparison, interactive timeline replay, metrics tables. |
| **Visual Simulation Window** | Python Tkinter | Double-click `run_window.bat`<br>or `python scripts/visual_simulation_window.py` | Standalone window showing Master Drone scouting first, then Swarm Drone targeted scanning. |

---

## 3. Architecture and Data Flow

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

- **Engine Independence:** Engine coordinates kinematics, battery drain, and task allocations without importing any UI or plotting libraries.
- **Drone Backend Abstraction:** Virtual drones operate via `SimBackend`, implementing a generic `DroneBackend` interface ready for future SITL/MAVLink adapters.
- **Pure Figures:** Dashboard visualizations are pure mathematical functions transforming recording frames into Plotly figures.

---

## 3. Directory Layout

```text
swarm/
├── README.md
├── pyproject.toml
├── run_studio.bat            # One-click launcher for Mission Studio (FastAPI + React)
├── run_studio.ps1            # PowerShell launcher for Mission Studio
├── run_dashboard.bat         # One-click launcher for Streamlit Dashboard
├── run_window.bat            # One-click launcher for Tkinter Visual Simulation
├── studio/                   # AgriVyaan Mission Studio (GIS & Multi-UAV Replay)
│   ├── backend/              # FastAPI + SQLModel backend (auto-UTM, optics, 10Hz sim)
│   ├── frontend/             # React 18 + Vite + Leaflet 60 FPS Canvas UI
│   ├── scripts/              # Development scripts
│   └── README.md             # Studio-specific documentation
├── assets/                   # Drone icons & farm maps
├── config/                   # Default scenario and simulator configurations
├── data/                     # Scenarios, cache, and simulation run results
├── docs/                     # Visual simulation guide
├── scripts/                  # Standalone CLI tools and simulation windows
├── src/                      # agrivyaan_swarm Python package
└── tests/                    # Pytest verification suites (34 tests)
```
│   ├── DASHBOARD.md
│   └── ROADMAP.md
├── src/agrivyaan_swarm/
│   ├── models/
│   ├── environment/
│   ├── backends/
│   ├── allocation/
│   ├── simulation/
│   ├── metrics/
│   ├── visualization/
│   └── dashboard/
├── tests/
└── scripts/
    ├── run_simulation.py
    └── compare_drones.py
```

---

## 4. Setup Guide (PowerShell / Windows)

```powershell
# Navigate to the swarm module
cd D:\college\PROJECTS\SIH\AgriVyaan\swarm

# Create Python 3.11+ virtual environment
py -3.11 -m venv .venv

# If script execution is restricted:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install package with all extras
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 5. Execution Commands

### 5.1 Run a Single Simulation
```powershell
python scripts/run_simulation.py --drones 3 --seed 42
```
Output artifacts are saved to `data/results/<run_id>/`:
- `recording.json` (Full state frames and timeline)
- `metrics.json` and `metrics.csv` (Computed KPIs)
- `events.csv` (Chronological event log)
- `summary_plot.png` (2D trajectory map)

### 5.2 Run Fleet Scaling Comparison
```powershell
python scripts/compare_drones.py --seeds 20
```
Runs 1, 2, and 3 drones across 20 paired seeds under Nominal, Energy-Constrained, and Hard Failure settings. Results are output to `data/results/comparison/`.

### 5.3 Run Automated Test Suite
```powershell
python -m pytest
```
Executes 27 automated tests covering battery feasibility, greedy allocation, fault recovery, geo round-trip, invariants, and Streamlit `AppTest` smoke verification.

### 5.4 Launch Interactive Dashboard
```powershell
streamlit run src/agrivyaan_swarm/dashboard/app.py
```
Opens the web dashboard in your browser (`http://localhost:8501`).

---

## 6. Key Simulation Assumptions & Current Limitations

1. **Energy Model:** Linear travel rate ($1.0\text{ EU/m}$) and linear inspection burn ($0.5\text{ EU/s}$) with a $20\%$ reserve floor and a $1.1\times$ safety factor.
2. **Kinematics:** Simple linear velocity without acceleration limits or wind disturbances. Drones do not collide or deconflict paths.
3. **Allocation:** Greedy nearest-feasible heuristic. Order bias favors lower drone IDs.
4. **No Mid-Mission Recharging:** Drones return to base once work is complete or battery drops to reserve levels.
