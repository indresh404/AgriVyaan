# AgriVyaan Mission Studio — Visual Multi-Drone Simulator

> [!IMPORTANT]
> **SIMULATION PROTOTYPE HONESTY STATEMENT:**
> This software is a simulation prototype for agricultural multi-UAV coordination. Detections represent synthetic user-marked ground truth zones, not real machine-learning detections. Microclimate temperature and relative humidity values are generated from a deterministic synthetic model. Battery energy consumption and flight duration are derived from an abstract physical kinematics model, not empirical battery flight testing. Capture images are cropped from satellite tiles or user-uploaded samples.
>
> **Known Imagery Limit:** Public satellite imagery (Esri World Imagery) has a resolution of ~0.3–0.6 m/pixel. High-altitude and detail zoom crops in this prototype cannot depict real microscopic leaf-level pathology resolution.

---

## 1. Overview & Architecture

AgriVyaan Mission Studio is a mission-control web platform where users can interactively configure precision-agriculture drone surveys on real satellite imagery, plan flight geometry, and watch multi-drone swarms execute surveys, handle low-battery handover to standby backup drones, discover hotspots, and conduct low-altitude micro-inspections.

```
studio/
├── backend/                  # FastAPI + SQLModel Backend
│   ├── app/
│   │   ├── camera/           # Optical footprints & grid subdivision
│   │   ├── crop_profiles/    # Crop profiles (potato growth stages, pathologies)
│   │   ├── environment/      # Synthetic spatial microclimate generator
│   │   ├── geo/              # Projections (pyproj Auto-UTM) & FieldGeometry (Shapely)
│   │   ├── imagery/          # Esri tile fetching, stitching, and crop extraction
│   │   ├── io/               # GeoJSON, KML, and full Project JSON serialization
│   │   ├── planning/         # Serpentine paths, fleet partitioning, turn penalties, energy
│   │   └── sim/              # 10 Hz deterministic discrete-time simulation & handover
│   └── tests/                # Pytest verification suite (14 passing tests)
├── frontend/                 # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── api/              # Strongly-typed client for FastAPI endpoints
│   │   ├── components/       # Permanent DisclaimerBanner & common UI
│   │   ├── lib/              # 60 FPS frame interpolation & unit formatting
│   │   ├── setup/            # 8-step Mission Setup Wizard & Leaflet SetupMap
│   │   ├── sim/              # Mission Replay: MapCanvasLayer, HUD, DroneCards, Timeline,
│   │   │                     # Filmstrip, ActivityFeed, AlgorithmPanel, CaptureInspector
│   │   └── store/            # Zustand reactive state stores
│   └── tests/                # Vitest unit test suite (7 passing tests)
├── scripts/                  # One-click startup scripts (`dev.ps1`, `dev.bat`)
└── assets/                   # README on tile attribution and licensing terms
```

---

## 2. Quick Start & Execution

### Prerequisites
- Python 3.10+ (tested with Python 3.11.0)
- Node.js 18+ (tested with Node v22.20.0 and npm 10.9.3)

### One-Click Launch (Windows)
Run the launcher script to start both backend (`:8000`) and frontend (`:5173`):

```powershell
# In PowerShell:
.\studio\scripts\dev.ps1

# Or double-click:
studio\scripts\dev.bat
```

### Manual Launch

**Backend:**
```bash
cd studio/backend
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be accessible at: `http://localhost:8000/docs`

**Frontend:**
```bash
cd studio/frontend
npm run dev
```
Interactive Studio UI will be accessible at: `http://localhost:5173`

---

## 3. Fixed Units & Core Formulas

| Quantity | Unit | Formula / Constraints |
|---|---|---|
| Distance / Altitude | metres ($m$) | $z \in [5.0, 120.0]\text{ m}$ (safety range) |
| Speed / Kinematics | $m/s$ | Cruise: $6.0\text{ m/s}$, Detail: $3.5\text{ m/s}$ |
| Time | seconds ($s$) | 10 Hz simulator step ($\Delta t = 0.1\text{ s}$) |
| Coordinates | WGS84 Lat/Lon | Auto-UTM zone projection via `pyproj` |
| Area | $m^2$, Hectares, Acres | Exact polygon area computed in projected UTM plane |
| Energy / Power | Wh, Watts | $E = \frac{P \cdot t}{3600}\text{ Wh}$; Turn penalty: $+2.0\text{ s}$ hover for turns $>30^\circ$ |
| Ground Sampling Distance | mm/pixel | $\text{GSD} = \text{altitude} \cdot \frac{S_w}{f \cdot I_w} \times 1000$ |
| Optical Footprint | metres ($m$) | $F_w = \text{altitude} \cdot \frac{S_w}{f},\quad F_h = \text{altitude} \cdot \frac{S_h}{f}$ |
| RTH Safety Energy | Wh | $E_{\text{return}} = \frac{d_{\text{base}}}{v_{\text{cruise}}} \cdot \frac{P_{\text{cruise}}}{3600} + t_{\text{desc}} \cdot \frac{P_{\text{climb}}}{3600} + E_{\text{reserve}}$ |

---

## 4. Test Verification Status

Every module and component was validated against real automated test suites:

- **Studio Backend Pytest:** 14/14 tests passed in `9.10s` (`studio/backend/tests/`)
  - `test_math_planning.py`: 6 passed (projections, footprints, grid cells, serpentine paths, fleet partitioning, turn penalties)
  - `test_api_persistence.py`: 5 passed (CRUD, project export/import, preview geometry, validation checklist, slippy tile caching)
  - `test_simulation_engine.py`: 3 passed (10 Hz simulation loop, low-battery RTH handover, Stage 2 micro-inspection)
- **Studio Frontend Vitest:** 7/7 tests passed in `1.39s` (`studio/frontend/src/tests/`)
  - `format.test.ts`: 5 passed (durations, distances, multi-unit area, GSD, coordinate strings)
  - `interpolate.test.ts`: 2 passed (angular wrapping across $0^\circ/360^\circ$ boundary, 60 FPS frame interpolation)
- **Frontend Bundle Build:** Vite built in `12.20s` with 0 TypeScript or bundling errors.
- **Existing Swarm Test Suite Integrity:** 34/34 tests passed in `8.28s` (`swarm/tests/`), confirming zero regression outside `studio/`.
