"""AgriVyaan Ground Control Station (GCS) — Precision Multi-UAV Swarm Simulation.

A standalone, professional native Python desktop window for agricultural multi-drone coordination.

Core Product Concept:
  1. Crop Field Setup & Flight Height Controls:
     - Pure top-down agricultural crop imagery (Potato canopy, natural soil rows). No satellite imagery.
     - Flight height controls: Scouting Altitude (15m - 50m) and Detailed Inspection Altitude (6m - 20m).
     - Camera footprint formula: W = 2 * h * tan(θx / 2), H = 2 * h * tan(θy / 2).
     - Square scanning zones: The farm area is divided into multiple square zones whose size
       and coverage automatically scale with drone flight height!
  2. Manual Node Placement (3 Types & 3 Sizes):
     - 🟡 Yellowish Node: Chlorosis / Nitrogen Deficiency (Evidence: crop_yellowish.jpeg)
     - 🟤 Brown Node: Stunted Canopy / Necrotic Foliage / Weak Growth (Evidence: crop_growth.jpeg)
     - 🔴 Disease Node: Fungal Blight Infection (Evidence: crop_early_blight.jpeg)
     - Sizing controls: Small (6m), Medium (12m), Large (20m) with live radius rendering.
  3. Two-Stage Detection Architecture:
     - Stage A (Master Scout): Surveys square zones at scouting altitude.
       Detects YELLOWISH and BROWN nodes ONLY as candidate anomalies. Does NOT confirm disease.
     - Stage B (Multi-Drone Investigation): Swarm fleet flies at lower altitude to investigate
       candidates, confirming/classifying underlying disease symptoms (Early Blight / Late Blight).
  4. Smooth, Restrained Heatmap:
     - High-resolution continuous Gaussian density blend (NO blocky pixelated squares, NO oversaturated yellow).
     - Healthy scanned canopy shows subtle natural translucent green.
     - Candidate/disease zones show smooth amber to crimson gradients only at the anomaly cores.
     - Heatmap toggle and opacity controls.
  5. Multi-Drone Fleet (Up to 10 Drones):
     - Fleet sizing from 1 to 10 drones (1 Master Scout + 1 to 9 Swarm Micro-Inspectors).
     - Distinct color-blind safe palette for all 10 drones.
     - Random Initial Low-Battery Scenarios (15-28%) with autonomous RTH and task handover.
     - Collision avoidance: Automatic separation monitoring, holding position, and safe yield.
"""

from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Fix Windows Python virtualenv TCL/TK paths if not configured
if sys.platform.startswith("win"):
    base_tcl = Path(sys.base_prefix) / "tcl"
    tcl_dir = base_tcl / "tcl8.6"
    tk_dir = base_tcl / "tk8.6"
    if tcl_dir.exists() and "TCL_LIBRARY" not in os.environ:
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir.exists() and "TK_LIBRARY" not in os.environ:
        os.environ["TK_LIBRARY"] = str(tk_dir)

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

# Project root path setup
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

# Base GPS Reference Point (WGS84)
ORIGIN_LAT = 18.52043
ORIGIN_LON = 73.85671

CROP_PROFILES = {
    "Potato (Solanum tuberosum)": {
        "icon": "🥔",
        "row_spacing_m": 0.75,
        "alt_survey_m": 25.0,
        "alt_detail_m": 12.0,
        "gsd_mm": 3.75,
        "vulnerabilities": ["Early Blight", "Late Blight", "Chlorosis", "Weak Canopy"],
    },
    "Corn / Maize (Zea mays)": {
        "icon": "🌽",
        "row_spacing_m": 0.76,
        "alt_survey_m": 30.0,
        "alt_detail_m": 14.0,
        "gsd_mm": 4.70,
        "vulnerabilities": ["Northern Corn Leaf Blight", "Stunted Growth", "Chlorosis"],
    },
    "Wheat (Triticum aestivum)": {
        "icon": "🌾",
        "row_spacing_m": 0.20,
        "alt_survey_m": 20.0,
        "alt_detail_m": 10.0,
        "gsd_mm": 3.38,
        "vulnerabilities": ["Rust Fungus", "Chlorosis", "Stunted Canopy"],
    },
    "Tomato (Solanum lycopersicum)": {
        "icon": "🍅",
        "row_spacing_m": 1.20,
        "alt_survey_m": 18.0,
        "alt_detail_m": 8.0,
        "gsd_mm": 2.80,
        "vulnerabilities": ["Early Blight", "Septoria Leaf Spot", "Aphids"],
    },
    "Soybean (Glycine max)": {
        "icon": "🌱",
        "row_spacing_m": 0.38,
        "alt_survey_m": 22.0,
        "alt_detail_m": 11.0,
        "gsd_mm": 3.75,
        "vulnerabilities": ["Frogeye Leaf Spot", "Sudden Death Syndrome", "Stunted Canopy"],
    },
}

# The 3 user-specified node types: Yellowish, Brown, Disease
NODE_TYPES = {
    "yellowish": {
        "key": "yellowish",
        "name": "Yellowish Foliage",
        "badge": "🟡 Yellowish",
        "color": "#eab308",
        "outline": "#fef08a",
        "file": "crop_yellowish.jpeg",
        "severity": 0.76,
        "description": "Leaf Chlorosis & Nitrogen Nutrient Deficiency",
        "is_scout_detectable": True,  # Stage A: Master scout detects this!
    },
    "growth": {
        "key": "growth",
        "name": "Brown / Less Growth",
        "badge": "🟤 Brown (Stunted)",
        "color": "#92400e",
        "outline": "#fcd34d",
        "file": "crop_growth.jpeg",
        "severity": 0.68,
        "description": "Stunted Canopy Growth, Necrosis & Viral Dwarfism",
        "is_scout_detectable": True,  # Stage A: Master scout detects this!
    },
    "disease": {
        "key": "disease",
        "name": "Disease Infection",
        "badge": "🔴 Disease",
        "color": "#dc2626",
        "outline": "#fecaca",
        "file": "crop_early_blight.jpeg",
        "severity": 0.94,
        "description": "Alternaria Fungal Blight Lesion (Confirmed by Swarm)",
        "is_scout_detectable": False,  # Stage B ONLY: Multi-drone detailed inspection confirms this!
    },
}

# Node Sizes: Small, Medium, Large
NODE_SIZES = {
    "small": {"label": "Small", "radius_m": 6.0, "icon": "S"},
    "medium": {"label": "Medium", "radius_m": 12.0, "icon": "M"},
    "large": {"label": "Large", "radius_m": 20.0, "icon": "L"},
}

# 10 Distinct Color-Blind Safe Drone Colors
FLEET_COLORS = [
    "#0284c7",  # D0: Master Scout (Sky Blue)
    "#10b981",  # D1: Emerald Green
    "#ec4899",  # D2: Pink
    "#f59e0b",  # D3: Amber Orange
    "#8b5cf6",  # D4: Purple
    "#06b6d4",  # D5: Cyan
    "#f97316",  # D6: Coral Orange
    "#14b8a6",  # D7: Teal
    "#e11d48",  # D8: Rose Red
    "#84cc16",  # D9: Lime Green
]


def metres_to_gps(xm: float, ym: float) -> Tuple[float, float]:
    """Convert local Cartesian metres (0..100) to WGS84 GPS latitude and longitude."""
    lat = ORIGIN_LAT + (ym / 111320.0)
    lon = ORIGIN_LON + (xm / (111320.0 * math.cos(math.radians(ORIGIN_LAT))))
    return round(lat, 5), round(lon, 5)


def calculate_polygon_area(vertices: List[Tuple[float, float]]) -> float:
    """Exact planar polygon survey area in m² using the Shoelace formula."""
    n = len(vertices)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0


def calculate_polygon_perimeter(vertices: List[Tuple[float, float]]) -> float:
    """Calculate the perimeter length in metres of a polygon."""
    n = len(vertices)
    if n < 2:
        return 0.0
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = vertices[j][0] - vertices[i][0]
        dy = vertices[j][1] - vertices[i][1]
        perim += math.hypot(dx, dy)
    return perim


class SquareZone:
    """Represents a square scanning zone in the farm area scaled by drone flight height."""

    def __init__(self, zone_id: int, x_min: float, y_min: float, x_max: float, y_max: float):
        self.id = zone_id
        self.x_min = x_min
        self.y_min = y_min
        self.x_max = x_max
        self.y_max = y_max
        self.center_x = (x_min + x_max) / 2.0
        self.center_y = (y_min + y_max) / 2.0
        self.status = "UNASSIGNED"  # UNASSIGNED | ASSIGNED | SCANNING | SCANNED
        self.assigned_drone_id: Optional[int] = None
        self.coverage_pct = 0.0


class FieldNode:
    """Represents an anomaly node (Yellowish, Brown, or Disease) with variable size."""

    def __init__(self, node_id: int, node_type_key: str, x: float, y: float, size_key: str = "medium"):
        self.id = node_id
        self.type_key = node_type_key
        self.type_info = NODE_TYPES.get(node_type_key, NODE_TYPES["yellowish"])
        self.size_key = size_key
        self.size_info = NODE_SIZES.get(size_key, NODE_SIZES["medium"])
        self.x = x
        self.y = y
        self.radius_m = self.size_info["radius_m"]
        self.gps_lat, self.gps_lon = metres_to_gps(x, y)

        # Stage A & B State Tracking
        self.discovered = False       # Set to True when detected
        self.is_candidate = False     # Flagged by Master Scout as suspicious candidate
        self.inspected = False        # Verified by Swarm investigation drone
        self.assigned_drone_id: Optional[int] = None
        self.rescan_progress = 0.0
        self.confirmed_disease_diagnosis: Optional[str] = None

    @property
    def name(self) -> str:
        return self.type_info["name"]

    @property
    def color(self) -> str:
        return self.type_info["color"]

    @property
    def file(self) -> str:
        return self.type_info["file"]

    @property
    def severity(self) -> float:
        return self.type_info["severity"]

    @property
    def info(self) -> dict:
        return self.type_info


class VirtualUAV:
    """Represents a virtual UAV with kinematics, altitude, collision avoidance, and battery."""

    def __init__(self, drone_id: int, is_master: bool, x: float, y: float, altitude_m: float = 25.0, max_speed: float = 6.5):
        self.id = drone_id
        self.is_master = is_master
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.heading_deg = 0.0
        self.altitude_m = altitude_m
        self.max_speed = max_speed
        self.status = "STANDBY"
        self.battery_eu = 500.0        # Energy units (Wh)
        self.max_battery_eu = 500.0
        self.current_task_id: Optional[int] = None
        self.assigned_zone_id: Optional[int] = None
        self.trail: List[Tuple[float, float]] = []
        self.holding_position = False  # Collision avoidance hold
        self.holding_reason = ""


class AgriVyaanSimulationApp:
    """Main Ground Control Station (GCS) Multi-Drone Precision Agriculture Simulation."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AgriVyaan Ground Control Station — Precision Multi-UAV Crop Scanner (60 FPS)")
        self.root.geometry("1480x930")
        self.root.minsize(1280, 820)
        self.root.configure(bg="#0b1120")

        # Field dimensions (100m x 100m coordinate space)
        self.field_w_m = 100.0
        self.field_h_m = 100.0
        self.canvas_w = 900
        self.canvas_h = 740
        self.base_m = (6.0, 6.0)

        # Drone Flight Height Controls & Optics
        self.scout_altitude_m = 25.0      # Master Scout height (15m - 50m)
        self.detail_altitude_m = 12.0     # Swarm Inspection height (6m - 20m)
        self.camera_fov_x_deg = 65.0      # Horizontal Camera FOV
        self.camera_fov_y_deg = 50.0      # Vertical Camera FOV

        # Multiple Square Scanning Zones Grid (Scales with flight height)
        self.square_zones: List[SquareZone] = []
        self.active_zone_size_m = 22.0

        # Map Zoom and Pan State
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.is_panning = False
        self.pan_start_x = 0.0
        self.pan_start_y = 0.0
        self.active_tool_mode = "edit"

        # Cursor Position Tracker
        self.cursor_xm = 50.0
        self.cursor_ym = 50.0
        self.cursor_lat = ORIGIN_LAT
        self.cursor_lon = ORIGIN_LON

        # Simulation clock
        self.sim_time = 0.0
        self.is_running = False
        self.sim_speed = 1.0

        # Guided Step Wizard:
        # 1: Crop Field & Altitude Setup (Square Zones)
        # 2: Manual Node Placement (3 Types & 3 Sizes)
        # 3: Flight Path & Zone Corridors
        # 4: Fleet Configuration (Up to 10 Drones & Low Battery Scenarios)
        # 5: Live Simulation & Two-Stage Anomaly Discovery
        self.wizard_step = 1

        # Selected Crop Profile
        self.selected_crop_name = "Potato (Solanum tuberosum)"

        # Active Node Placement Controls
        self.active_place_node_type = "yellowish"  # "yellowish" | "growth" | "disease"
        self.active_place_node_size = "medium"     # "small" | "medium" | "large"

        # Background Map Mode (Pure Crop Imagery ONLY — No Satellite!)
        self.active_farm_source = "crop_image.png"

        # Configurable Swarm Fleet size (1 Master + up to 9 Swarm Drones = 10 Drones max)
        self.num_swarm_drones = 2
        self.enable_random_low_batt = True

        # Heatmap Display Settings
        self.heatmap_enabled = True
        self.heatmap_opacity = 0.45

        # Geofence boundary vertices (1-Hectare polygon)
        self.boundary_vertices: List[Tuple[float, float]] = [
            (10.0, 10.0),
            (10.0, 90.0),
            (90.0, 90.0),
            (90.0, 10.0),
        ]

        # Waypoints for Master Drone
        self.lawnmower_waypoints: List[Tuple[float, float]] = []
        self.current_wp_idx = 0

        # Manually placed detected nodes (Yellowish, Brown, Disease)
        self.anomalies: List[FieldNode] = []

        # Survey coverage tracking grid (1m resolution)
        self.covered_cells: set[Tuple[int, int]] = set()

        # Radar animation counters
        self.comms_pulse = 0.0
        self.radar_scan_angle = 0.0
        self.radar_pulse_radius = 0.0
        self.radar_sweep_cone = 0.0
        self.radar_sweep_dir = 1.0

        # Mission Simulation Phase:
        # 0: Standby at base
        # 1: Master Drone Scouting (Detects Yellowish & Brown Candidates ONLY)
        # 2: Swarm Fleet Detailed Micro-Inspection (Classifies & Confirms Disease)
        # 3: Mission Accomplished
        self.mission_phase = 0

        # Background Imagery Cache for smooth dynamic zoom
        self.raw_farm_crop: Optional[Image.Image] = None
        self.cached_bg_photo: Optional[ImageTk.PhotoImage] = None
        self.cached_bg_size: Optional[Tuple[int, int]] = None
        self.cached_bg_source: Optional[str] = None

        # Load Visual Media Assets
        self.assets_dir = ROOT_DIR / "assets"
        self.load_assets()

        # Generate Initial Square Zones
        self.generate_square_zones()

        # Construct UI layout
        self.build_ui()

        # Setup initial default nodes (for tests & demo)
        self.setup_default_nodes()
        self.generate_lawnmower_path()
        self.reset_simulation()

        # Start 60 FPS hardware loop
        self.root.after(16, self.animation_tick)

    def load_assets(self):
        """Pre-load background textures, raw PIL images for zoom re-scaling, and icons."""
        crop_path = self.assets_dir / "crop_image.png"
        try:
            if crop_path.exists():
                self.raw_farm_crop = Image.open(crop_path)
        except Exception as e:
            print(f"Warning: Failed to load raw crop imagery: {e}")

        self.farm_img_crop = self.safe_load_image(crop_path, (self.canvas_w, self.canvas_h))

        # Drone icons
        self.icon_master = self.safe_load_image(self.assets_dir / "master_drone.png", (52, 52))
        self.icon_swarm = self.safe_load_image(self.assets_dir / "drone.png", (38, 38))

        # Evidence photos for node types
        self.evidence_photos = {
            "crop_yellowish.jpeg": self.safe_load_image(self.assets_dir / "crop_yellowish.jpeg", (240, 150)),
            "crop_growth.jpeg": self.safe_load_image(self.assets_dir / "crop_growth.jpeg", (240, 150)),
            "crop_early_blight.jpeg": self.safe_load_image(self.assets_dir / "crop_early_blight.jpeg", (240, 150)),
        }

    def safe_load_image(self, path: Path, size: Tuple[int, int]) -> Optional[ImageTk.PhotoImage]:
        """Safely load and resize image, returning Tk PhotoImage."""
        try:
            if path.exists():
                img = Image.open(path)
                img = img.resize(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Warning: Failed to load asset {path}: {e}")
        return None

    def calculate_camera_footprint(self, altitude_m: float) -> Tuple[float, float]:
        """Calculate ground camera footprint width and height in metres from altitude and FOV."""
        rad_x = math.radians(self.camera_fov_x_deg)
        rad_y = math.radians(self.camera_fov_y_deg)
        fw = 2.0 * altitude_m * math.tan(rad_x / 2.0)
        fh = 2.0 * altitude_m * math.tan(rad_y / 2.0)
        return round(fw, 1), round(fh, 1)

    def generate_square_zones(self):
        """Generate square scanning zones inside the farm boundary based on flight height."""
        fw, fh = self.calculate_camera_footprint(self.scout_altitude_m)
        # Zone size matches camera footprint with standard 15% overlap
        zone_sz = max(10.0, min(40.0, round(fw * 0.85, 1)))
        self.active_zone_size_m = zone_sz

        xs = [v[0] for v in self.boundary_vertices]
        ys = [v[1] for v in self.boundary_vertices]
        min_x, max_x = min(xs) + 2.0, max(xs) - 2.0
        min_y, max_y = min(ys) + 2.0, max(ys) - 2.0

        if max_x <= min_x or max_y <= min_y:
            return

        self.square_zones = []
        zone_id = 1
        y_curr = min_y
        while y_curr < max_y:
            x_curr = min_x
            y_next = min(max_y, y_curr + zone_sz)
            while x_curr < max_x:
                x_next = min(max_x, x_curr + zone_sz)
                z = SquareZone(zone_id, x_curr, y_curr, x_next, y_next)
                self.square_zones.append(z)
                zone_id += 1
                x_curr += zone_sz
            y_curr += zone_sz

    def build_ui(self):
        """Construct full Ground Control Station interface."""
        # 1. Honesty Simulation Banner
        banner = tk.Label(
            self.root,
            text="SIMULATION ONLY — Synthetic crop anomalies and abstract energy model. Detections are candidate marks, not actual laboratory diagnoses.",
            bg="#0369a1",
            fg="#f0f9ff",
            font=("Segoe UI", 9, "bold"),
            pady=3,
        )
        banner.pack(fill=tk.X)

        # 2. Step Progress Navigation Bar (Wizard Stepper)
        self.stepper_frame = tk.Frame(self.root, bg="#0f172a", pady=6, padx=12)
        self.stepper_frame.pack(fill=tk.X)

        self.step_buttons = []
        steps_info = [
            ("1. Crop Field & Height", 1),
            ("2. Place 3 Node Types", 2),
            ("3. Square Zones & Path", 3),
            ("4. Fleet Sizing (1-10)", 4),
            ("🚀 5. Staged Simulation", 5),
        ]
        for title, step_num in steps_info:
            btn = tk.Button(
                self.stepper_frame,
                text=title,
                command=lambda s=step_num: self.set_wizard_step(s),
                bg="#1e293b",
                fg="#94a3b8",
                activebackground="#0284c7",
                activeforeground="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT,
                padx=12,
                pady=4,
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.step_buttons.append(btn)

        # Right: Step Navigation (Back / Next)
        self.btn_next_step = tk.Button(
            self.stepper_frame,
            text="Next Step ➔",
            command=self.advance_step,
            bg="#059669",
            fg="#ffffff",
            activebackground="#047857",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=4,
        )
        self.btn_next_step.pack(side=tk.RIGHT, padx=4)

        self.btn_prev_step = tk.Button(
            self.stepper_frame,
            text="◀ Back",
            command=self.retreat_step,
            bg="#334155",
            fg="#e2e8f0",
            activebackground="#475569",
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            padx=10,
            pady=4,
        )
        self.btn_prev_step.pack(side=tk.RIGHT, padx=2)

        # 3. Contextual Toolbar
        self.toolbar = tk.Frame(self.root, bg="#1e293b", pady=6, padx=12)
        self.toolbar.pack(fill=tk.X)

        # 4. Live Metric & Status Ribbon
        self.metric_ribbon = tk.Frame(self.root, bg="#0b1329", pady=4, padx=14)
        self.metric_ribbon.pack(fill=tk.X)

        self.lbl_area_metric = tk.Label(
            self.metric_ribbon,
            text="Survey Area: 6,400 m² (0.64 Ha) | Altitude: 25.0m | Footprint: 32.5m × 23.3m | Zones: 16 Squares",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0b1329",
        )
        self.lbl_area_metric.pack(side=tk.LEFT)

        self.lbl_node_counts = tk.Label(
            self.metric_ribbon,
            text="Nodes Placed: 0 Yellowish | 0 Brown | 0 Disease",
            font=("Segoe UI", 9, "bold"),
            fg="#facc15",
            bg="#0b1329",
        )
        self.lbl_node_counts.pack(side=tk.LEFT, padx=18)

        self.lbl_tool_hint = tk.Label(
            self.metric_ribbon,
            text="Step 1: Set Farm Boundary & Altitude on Crop Field",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#0b1329",
        )
        self.lbl_tool_hint.pack(side=tk.RIGHT)

        # 5. Main Workspace (Canvas on Left, Telemetry & Evidence HUD on Right)
        main_pane = tk.Frame(self.root, bg="#0b1120")
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 8))

        # Canvas Frame Container
        self.left_frame = tk.Frame(main_pane, bg="#1e293b", bd=1, relief=tk.SOLID)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.left_frame, width=self.canvas_w, height=self.canvas_h, bg="#064e3b", highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Background Image Item (Crop Imagery)
        init_img = self.farm_img_crop if self.farm_img_crop else None
        self.cached_bg_photo = init_img
        self.cached_bg_size = (self.canvas_w, self.canvas_h)
        self.cached_bg_source = "crop_image.png"
        self.bg_img_item = self.canvas.create_image(0, 0, image=init_img, anchor=tk.NW, tags="bg_layer")

        # Floating Map Navigation & Controls Overlay (Top-Right)
        self.map_nav_box = tk.Frame(self.left_frame, bg="#090d16", bd=1, relief=tk.SOLID, padx=6, pady=4)
        self.map_nav_box.place(relx=0.985, rely=0.015, anchor=tk.NE)

        # Row 1: Zoom In, Zoom Level, Zoom Out, Fit, Reset
        row1 = tk.Frame(self.map_nav_box, bg="#090d16")
        row1.pack(fill=tk.X, pady=2)

        self.btn_zoom_in = tk.Button(
            row1, text="＋", command=lambda: self.zoom_by(1.25), bg="#1e293b", fg="#38bdf8",
            activebackground="#0284c7", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, width=3, padx=2, pady=1
        )
        self.btn_zoom_in.pack(side=tk.LEFT, padx=1)

        self.lbl_zoom_val = tk.Label(
            row1, text="100%", bg="#090d16", fg="#f8fafc", font=("Consolas", 9, "bold"), width=5
        )
        self.lbl_zoom_val.pack(side=tk.LEFT, padx=2)

        self.btn_zoom_out = tk.Button(
            row1, text="－", command=lambda: self.zoom_by(0.80), bg="#1e293b", fg="#38bdf8",
            activebackground="#0284c7", activeforeground="#ffffff", font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, width=3, padx=2, pady=1
        )
        self.btn_zoom_out.pack(side=tk.LEFT, padx=1)

        self.btn_fit_field = tk.Button(
            row1, text="⛶ Fit", command=self.fit_to_field, bg="#064e3b", fg="#34d399",
            activebackground="#059669", activeforeground="#ffffff", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=6, pady=1
        )
        self.btn_fit_field.pack(side=tk.LEFT, padx=3)

        self.btn_reset_zoom = tk.Button(
            row1, text="⟲ Reset", command=self.reset_zoom, bg="#334155", fg="#cbd5e1",
            activebackground="#475569", font=("Segoe UI", 8), relief=tk.FLAT, padx=6, pady=1
        )
        self.btn_reset_zoom.pack(side=tk.LEFT, padx=1)

        # Row 2: Tool Mode (Edit / Pan) & Heatmap Toggle
        row2 = tk.Frame(self.map_nav_box, bg="#090d16")
        row2.pack(fill=tk.X, pady=(3, 1))

        self.btn_mode_edit = tk.Button(
            row2, text="✥ Edit", command=lambda: self.set_tool_mode("edit"),
            bg="#0284c7", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=1
        )
        self.btn_mode_edit.pack(side=tk.LEFT, padx=1)

        self.btn_mode_pan = tk.Button(
            row2, text="🖐 Pan", command=lambda: self.set_tool_mode("pan"),
            bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8), relief=tk.FLAT, padx=6, pady=1
        )
        self.btn_mode_pan.pack(side=tk.LEFT, padx=1)

        self.btn_toggle_heatmap = tk.Button(
            row2, text="🌿 Heatmap: ON", command=self.toggle_heatmap,
            bg="#064e3b", fg="#34d399", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6, pady=1
        )
        self.btn_toggle_heatmap.pack(side=tk.LEFT, padx=3)

        # Row 3: Live Cursor Coordinate Tracker
        row3 = tk.Frame(self.map_nav_box, bg="#090d16")
        row3.pack(fill=tk.X, pady=(2, 0))

        self.lbl_cursor_coords = tk.Label(
            row3, text="Cursor: X: 50.0m, Y: 50.0m | GPS: 18.52088°N, 73.85718°E",
            bg="#090d16", fg="#38bdf8", font=("Consolas", 8), anchor=tk.E
        )
        self.lbl_cursor_coords.pack(fill=tk.X)

        # Canvas Mouse & Keyboard Bindings
        self.canvas.bind("<Button-1>", self.on_canvas_left_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_left_release)

        self.canvas.bind("<Button-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)

        self.canvas.bind("<Button-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_pan_end)

        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_by(1.15, e.x, e.y))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_by(1.0 / 1.15, e.x, e.y))

        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Keyboard Accelerators
        self.root.bind("<plus>", lambda e: self.zoom_by(1.25))
        self.root.bind("<equal>", lambda e: self.zoom_by(1.25))
        self.root.bind("<minus>", lambda e: self.zoom_by(0.80))
        self.root.bind("<Home>", lambda e: self.reset_zoom())
        self.root.bind("<f>", lambda e: self.fit_to_field())
        self.root.bind("<F>", lambda e: self.fit_to_field())

        # Right Telemetry and Crop Evidence Panel
        right_frame = tk.Frame(main_pane, width=470, bg="#1e293b", bd=1, relief=tk.SOLID)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))

        # Panel Header Badge
        self.lbl_phase_badge = tk.Label(
            right_frame,
            text="STEP 1: CROP FIELD SETUP & ALTITUDE CONFIGURATION",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="white",
            pady=6,
        )
        self.lbl_phase_badge.pack(fill=tk.X)

        # Flight Status Cards Container
        status_frame = tk.Frame(right_frame, bg="#0f172a", pady=8, padx=12, bd=1, relief=tk.SOLID)
        status_frame.pack(fill=tk.X, padx=8, pady=(6, 4))

        self.lbl_clock = tk.Label(
            status_frame, text="Mission Clock: 0.0 s", font=("Segoe UI", 10, "bold"), fg="#f8fafc", bg="#0f172a"
        )
        self.lbl_clock.pack(anchor=tk.W)

        # Master Drone Telemetry Card with Battery Gauge
        master_card = tk.Frame(status_frame, bg="#1e293b", padx=8, pady=6, bd=1, relief=tk.RIDGE)
        master_card.pack(fill=tk.X, pady=4)

        self.lbl_master_status = tk.Label(
            master_card,
            text="Master Drone (D0): Standby at Launchpad",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#1e293b",
        )
        self.lbl_master_status.pack(anchor=tk.W)

        self.lbl_master_battery = tk.Label(
            master_card,
            text="Battery: [██████████] 100% (500 Wh) | Alt: 25.0m | Spd: 0.0 m/s",
            font=("Consolas", 8),
            fg="#34d399",
            bg="#1e293b",
        )
        self.lbl_master_battery.pack(anchor=tk.W, pady=(2, 0))

        # Swarm Fleet Telemetry Card (Multi-Drone Fleet)
        swarm_card = tk.Frame(status_frame, bg="#1e293b", padx=8, pady=6, bd=1, relief=tk.RIDGE)
        swarm_card.pack(fill=tk.X, pady=2)

        self.lbl_swarm_status = tk.Label(
            swarm_card,
            text="Swarm Fleet: Standby (Awaiting Master Scout Candidates)",
            font=("Segoe UI", 9, "bold"),
            fg="#f472b6",
            bg="#1e293b",
        )
        self.lbl_swarm_status.pack(anchor=tk.W)

        self.lbl_swarm_details = tk.Label(
            swarm_card,
            text="D1: [██████████] 100% | D2: [██████████] 100%",
            font=("Consolas", 8),
            fg="#cbd5e1",
            bg="#1e293b",
        )
        self.lbl_swarm_details.pack(anchor=tk.W, pady=(2, 0))

        # Wireless Mesh Network & Collision Avoidance Monitor
        tk.Label(
            right_frame, text="Wireless Mesh & Collision Avoidance",
            font=("Segoe UI", 9, "bold"), bg="#334155", fg="#f1f5f9", pady=3
        ).pack(fill=tk.X, pady=(4, 2))

        comms_frame = tk.Frame(right_frame, bg="#090d16", padx=8, pady=4, bd=1, relief=tk.RIDGE)
        comms_frame.pack(fill=tk.X, padx=8)

        self.lbl_mesh_stats = tk.Label(
            comms_frame,
            text="Mesh Link: ACTIVE (5.8 GHz P2P, Latency: 12ms)\nSeparation: SAFE (>6.0m Horizon, Collision Avoidance ACTIVE)",
            font=("Consolas", 8),
            fg="#38bdf8",
            bg="#090d16",
            justify=tk.LEFT,
        )
        self.lbl_mesh_stats.pack(anchor=tk.W)

        # Active Rescan Crop Pathology Evidence Box
        tk.Label(
            right_frame, text="Active Rescan — Crop Pathology Evidence",
            font=("Segoe UI", 9, "bold"), bg="#334155", fg="#f1f5f9", pady=3
        ).pack(fill=tk.X, pady=(6, 2))

        self.evidence_box = tk.Frame(right_frame, bg="#090d16", bd=1, relief=tk.GROOVE, padx=8, pady=4)
        self.evidence_box.pack(fill=tk.X, padx=8)

        self.lbl_evidence_img = tk.Label(
            self.evidence_box, bg="#1e293b", width=30, height=7, text="Awaiting Rescan Phase...", fg="#94a3b8"
        )
        self.lbl_evidence_img.pack(pady=3)

        self.lbl_evidence_title = tk.Label(
            self.evidence_box, text="Stage A: Master Drone Scouting (Yellowish & Brown Only)",
            font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#090d16"
        )
        self.lbl_evidence_title.pack(pady=1)

        self.lbl_evidence_severity = tk.Label(
            self.evidence_box, text="Severity Meter: [░░░░░░░░░░] 0%",
            font=("Consolas", 8, "bold"), fg="#94a3b8", bg="#090d16"
        )
        self.lbl_evidence_severity.pack(pady=1)

        self.lbl_evidence_details = tk.Label(
            self.evidence_box,
            text="Master Drone scans square zones for Yellowish / Brown candidates.\nSwarm investigation drones deploy to diagnose disease.",
            font=("Segoe UI", 8),
            justify=tk.LEFT,
            bg="#090d16",
            fg="#94a3b8",
        )
        self.lbl_evidence_details.pack(pady=2)

        # Highlighted Mission Log Terminal
        tk.Label(
            right_frame, text="Live GCS Mission & Telemetry Log",
            font=("Segoe UI", 9, "bold"), bg="#334155", fg="#f1f5f9", pady=3
        ).pack(fill=tk.X, pady=(6, 2))

        log_container = tk.Frame(right_frame, bg="#1e293b")
        log_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        scroll = tk.Scrollbar(log_container)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.event_text = tk.Text(
            log_container,
            font=("Consolas", 8),
            bg="#050811",
            fg="#f8fafc",
            wrap=tk.WORD,
            bd=1,
            relief=tk.SOLID,
            yscrollcommand=scroll.set,
            height=10,
            state=tk.DISABLED,
        )
        self.event_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.event_text.yview)

        # Log Badges
        self.event_text.tag_configure("time", foreground="#94a3b8")
        self.event_text.tag_configure("badge_master", foreground="#38bdf8", background="#0c4a6e", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_swarm", foreground="#f472b6", background="#4a044e", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_alert", foreground="#fbbf24", background="#451a03", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_comms", foreground="#34d399", background="#064e3b", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_fault", foreground="#f43f5e", background="#4c0519", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_gcs", foreground="#f1f5f9", background="#334155", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("badge_col", foreground="#fbbf24", background="#78350f", font=("Consolas", 8, "bold"))
        self.event_text.tag_configure("msg_text", foreground="#f8fafc")

        self.update_stepper_ui()
        self.build_step_controls()

    def toggle_heatmap(self):
        """Toggle heatmap visualization on/off."""
        self.heatmap_enabled = not self.heatmap_enabled
        if self.heatmap_enabled:
            self.btn_toggle_heatmap.config(text="🌿 Heatmap: ON", bg="#064e3b", fg="#34d399")
        else:
            self.btn_toggle_heatmap.config(text="🌿 Heatmap: OFF", bg="#334155", fg="#94a3b8")

    def set_tool_mode(self, mode: str):
        """Toggle between 'edit' and 'pan' mode."""
        self.active_tool_mode = mode
        if mode == "pan":
            self.btn_mode_pan.config(bg="#0284c7", fg="#ffffff", font=("Segoe UI", 8, "bold"))
            self.btn_mode_edit.config(bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8))
            self.canvas.config(cursor="fleur")
            self.lbl_tool_hint.config(text="Pan Mode: Click and drag anywhere to pan the map view.")
        else:
            self.btn_mode_edit.config(bg="#0284c7", fg="#ffffff", font=("Segoe UI", 8, "bold"))
            self.btn_mode_pan.config(bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8))
            cur = "crosshair" if self.wizard_step == 2 else "arrow"
            self.canvas.config(cursor=cur)
            self.update_step_tool_hint()

    def update_step_tool_hint(self):
        """Update ribbon tool hint according to active step."""
        step_hints = {
            1: "Step 1: Set Farm Boundary & Altitude (Notice square zones resize dynamically with height!).",
            2: f"Step 2: Place {NODE_TYPES[self.active_place_node_type]['badge']} ({NODE_SIZES[self.active_place_node_size]['label']}) on the field.",
            3: "Step 3: Review Square Scanning Zones and Auto-Generated Flight Path.",
            4: "Step 4: Configure Fleet (1-10 Drones) and Low Battery Scenarios.",
            5: "Step 5: Staged Execution: Master Drone scouts Yellowish/Brown -> Swarm drones inspect Disease!",
        }
        self.lbl_tool_hint.config(text=step_hints.get(self.wizard_step, ""))

    def on_altitude_changed(self, val=None):
        """Handle drone flight height adjustment and immediately update area cover on screen."""
        try:
            if val is not None:
                self.scout_altitude_m = float(val)
            elif hasattr(self, "slider_scout_alt"):
                self.scout_altitude_m = float(self.slider_scout_alt.get())

            if hasattr(self, "master_drone") and self.master_drone is not None:
                self.master_drone.altitude_m = self.scout_altitude_m

            self.generate_square_zones()
            self.generate_lawnmower_path()
            self.update_area_metrics()

            fw, fh = self.calculate_camera_footprint(self.scout_altitude_m)
            if hasattr(self, "lbl_slider_footprint"):
                self.lbl_slider_footprint.config(text=f"Coverage: {fw:.1f}m × {fh:.1f}m ({fw*fh:.0f} m²)")

            self.render_canvas()
            self.log_event(
                f"Flight Height updated to {self.scout_altitude_m:.1f}m -> Optical Footprint: {fw:.1f}m × {fh:.1f}m ({fw*fh:.0f} m²). Zones updated: {len(self.square_zones)} squares.",
                category="GCS",
            )
        except Exception:
            pass

    def build_step_controls(self):
        """Construct toolbar controls corresponding to the active wizard step."""
        for widget in self.toolbar.winfo_children():
            widget.destroy()

        # Step 1: Crop Field & Drone Flight Height Controls (Square Zones)
        if self.wizard_step == 1:
            if hasattr(self, "canvas") and self.active_tool_mode == "edit":
                self.canvas.config(cursor="arrow")

            tk.Label(self.toolbar, text="Crop Selection:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
            self.crop_combo = ttk.Combobox(self.toolbar, values=list(CROP_PROFILES.keys()), width=24, state="readonly")
            self.crop_combo.set(self.selected_crop_name)
            self.crop_combo.bind("<<ComboboxSelected>>", self.on_crop_changed)
            self.crop_combo.pack(side=tk.LEFT, padx=(0, 8))

            # Flight Height Setting Slider
            tk.Label(self.toolbar, text="Drone Height (Altitude):", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(4, 2))
            self.slider_scout_alt = tk.Scale(
                self.toolbar, from_=15.0, to=45.0, resolution=2.5, orient=tk.HORIZONTAL,
                bg="#1e293b", fg="#38bdf8", highlightthickness=0, length=130, command=self.on_altitude_changed
            )
            self.slider_scout_alt.set(self.scout_altitude_m)
            self.slider_scout_alt.pack(side=tk.LEFT, padx=(0, 4))

            # Live Footprint Metric Label right next to slider
            fw_init, fh_init = self.calculate_camera_footprint(self.scout_altitude_m)
            self.lbl_slider_footprint = tk.Label(
                self.toolbar, text=f"Coverage: {fw_init:.1f}m × {fh_init:.1f}m ({fw_init*fh_init:.0f} m²)",
                bg="#090d16", fg="#34d399", font=("Consolas", 8, "bold"), padx=6, pady=2, bd=1, relief=tk.SOLID
            )
            self.lbl_slider_footprint.pack(side=tk.LEFT, padx=(0, 8))

            tk.Button(self.toolbar, text="Clear Vertices", command=self.clear_boundary, bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)
            tk.Button(self.toolbar, text="Reset 1 Ha", command=self.reset_default_boundary, bg="#334155", fg="#38bdf8", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)

        # Step 2: Manual Placement of 3 Node Types with 3 Size Options
        elif self.wizard_step == 2:
            if hasattr(self, "canvas") and self.active_tool_mode == "edit":
                self.canvas.config(cursor="crosshair")

            tk.Label(self.toolbar, text="Node Type:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))

            # Node Type Selection
            self.btn_node_yellow = tk.Button(
                self.toolbar, text="🟡 Yellowish", command=lambda: self.select_place_node_type("yellowish"),
                bg="#854d0e" if self.active_place_node_type == "yellowish" else "#334155",
                fg="#fef08a", font=("Segoe UI", 8, "bold"),
                relief=tk.SUNKEN if self.active_place_node_type == "yellowish" else tk.FLAT, padx=6
            )
            self.btn_node_yellow.pack(side=tk.LEFT, padx=2)

            self.btn_node_brown = tk.Button(
                self.toolbar, text="🟤 Brown (Stunted)", command=lambda: self.select_place_node_type("growth"),
                bg="#78350f" if self.active_place_node_type == "growth" else "#334155",
                fg="#fde68a", font=("Segoe UI", 8, "bold"),
                relief=tk.SUNKEN if self.active_place_node_type == "growth" else tk.FLAT, padx=6
            )
            self.btn_node_brown.pack(side=tk.LEFT, padx=2)

            self.btn_node_disease = tk.Button(
                self.toolbar, text="🔴 Disease", command=lambda: self.select_place_node_type("disease"),
                bg="#991b1b" if self.active_place_node_type == "disease" else "#334155",
                fg="#fecaca", font=("Segoe UI", 8, "bold"),
                relief=tk.SUNKEN if self.active_place_node_type == "disease" else tk.FLAT, padx=6
            )
            self.btn_node_disease.pack(side=tk.LEFT, padx=2)

            # Node Size Selection (Small, Medium, Large)
            tk.Label(self.toolbar, text="Size:", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(10, 4))
            for skey, sinfo in NODE_SIZES.items():
                is_active = self.active_place_node_size == skey
                sbtn = tk.Button(
                    self.toolbar, text=f"{sinfo['icon']} ({sinfo['radius_m']:.0f}m)",
                    command=lambda k=skey: self.select_place_node_size(k),
                    bg="#0284c7" if is_active else "#334155",
                    fg="#ffffff" if is_active else "#cbd5e1",
                    font=("Segoe UI", 8, "bold" if is_active else "normal"),
                    relief=tk.SUNKEN if is_active else tk.FLAT, padx=5
                )
                sbtn.pack(side=tk.LEFT, padx=2)

            tk.Button(self.toolbar, text="↶ Undo", command=self.remove_last_node, bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=(8, 2))
            tk.Button(self.toolbar, text="🗑 Clear", command=self.clear_nodes, bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)
            tk.Button(self.toolbar, text="⚡ Add Demo", command=self.setup_default_nodes, bg="#0284c7", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=4)

        # Step 3: Flight Path & Square Zones
        elif self.wizard_step == 3:
            if hasattr(self, "canvas") and self.active_tool_mode == "edit":
                self.canvas.config(cursor="arrow")
            tk.Label(self.toolbar, text=f"Square Zones ({len(self.square_zones)} Squares):", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(self.toolbar, text="Re-compute Zone Paths", command=self.generate_lawnmower_path, bg="#0284c7", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=3)
            tk.Button(self.toolbar, text="Clear Path", command=self.clear_path, bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=3)

        # Step 4: Fleet Configuration (1 to 10 Drones) & Low Battery Scenarios
        elif self.wizard_step == 4:
            if hasattr(self, "canvas") and self.active_tool_mode == "edit":
                self.canvas.config(cursor="arrow")

            tk.Label(self.toolbar, text="Fleet Size:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(self.toolbar, text="1 Master Scout +", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

            self.spin_drones = ttk.Spinbox(self.toolbar, from_=1, to=9, width=3, command=self.on_drone_count_changed)
            self.spin_drones.set(str(self.num_swarm_drones))
            self.spin_drones.pack(side=tk.LEFT, padx=4)

            total_fleet = 1 + self.num_swarm_drones
            tk.Label(self.toolbar, text=f"Investigation Drones = {total_fleet} Total", bg="#1e293b", fg="#f472b6", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 12))

            # Random Low Battery Checkbox
            self.chk_low_batt = tk.Checkbutton(
                self.toolbar, text="Random Low Battery (15-28%)", command=self.toggle_random_low_batt,
                bg="#1e293b", fg="#facc15", selectcolor="#090d16", activebackground="#1e293b", activeforeground="#facc15",
                font=("Segoe UI", 8, "bold")
            )
            if self.enable_random_low_batt:
                self.chk_low_batt.select()
            self.chk_low_batt.pack(side=tk.LEFT, padx=(0, 14))

            tk.Button(self.toolbar, text="🚀 Ready: Launch Mission", command=lambda: self.set_wizard_step(5), bg="#059669", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12).pack(side=tk.LEFT)

        # Step 5: Active Swarm Fleet Simulation Execution
        elif self.wizard_step == 5:
            if hasattr(self, "canvas") and self.active_tool_mode == "edit":
                self.canvas.config(cursor="arrow")
            self.btn_start = tk.Button(self.toolbar, text="Start Mission", command=self.start_mission, bg="#059669", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12)
            self.btn_start.pack(side=tk.LEFT, padx=(0, 4))

            self.btn_play_pause = tk.Button(self.toolbar, text="Pause", command=self.toggle_play_pause, bg="#475569", fg="#ffffff", font=("Segoe UI", 9), relief=tk.FLAT, padx=8)
            self.btn_play_pause.pack(side=tk.LEFT, padx=3)

            tk.Button(self.toolbar, text="Reset", command=self.reset_simulation, bg="#475569", fg="#ffffff", font=("Segoe UI", 9), relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=3)

            # Altitude Flight Height Slider during mission
            tk.Label(self.toolbar, text="Alt:", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(8, 2))
            self.slider_scout_alt = tk.Scale(
                self.toolbar, from_=15.0, to=45.0, resolution=2.5, orient=tk.HORIZONTAL,
                bg="#1e293b", fg="#38bdf8", highlightthickness=0, length=90, command=self.on_altitude_changed
            )
            self.slider_scout_alt.set(self.scout_altitude_m)
            self.slider_scout_alt.pack(side=tk.LEFT, padx=(0, 6))

            # Speed selector
            tk.Label(self.toolbar, text="Speed:", bg="#1e293b", fg="#cbd5e1", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 2))
            self.speed_combo = ttk.Combobox(self.toolbar, values=["0.5x", "1.0x", "2.0x", "4.0x"], width=5, state="readonly")
            self.speed_combo.set(f"{self.sim_speed}x")
            self.speed_combo.bind("<<ComboboxSelected>>", self.on_speed_changed)
            self.speed_combo.pack(side=tk.LEFT)

            # Fault Injection
            tk.Button(self.toolbar, text="Fault Drone 1", command=self.inject_drone_failure, bg="#dc2626", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, padx=4)

        # Right Map View Selector (Crop Photo or Plain Grid — Zero Satellite!)
        tk.Label(self.toolbar, text="Map View:", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8)).pack(side=tk.RIGHT, padx=(6, 2))
        self.map_combo = ttk.Combobox(self.toolbar, values=["Aerial Crop Photo", "Plain Crop Grid"], width=16, state="readonly")
        current_map_label = "Aerial Crop Photo" if self.active_farm_source == "crop_image.png" else "Plain Crop Grid"
        self.map_combo.set(current_map_label)
        self.map_combo.bind("<<ComboboxSelected>>", self.on_map_changed)
        self.map_combo.pack(side=tk.RIGHT, padx=(0, 10))

    def select_place_node_type(self, node_type: str):
        """Switch active node type to place when clicking map."""
        self.active_place_node_type = node_type
        self.build_step_controls()
        info = NODE_TYPES[node_type]
        self.lbl_tool_hint.config(text=f"Ready: Click to place {info['badge']} ({info['description']})")

    def select_place_node_size(self, size_key: str):
        """Switch active node size (Small, Medium, Large)."""
        self.active_place_node_size = size_key
        self.build_step_controls()

    def toggle_random_low_batt(self):
        """Toggle random low battery injection."""
        self.enable_random_low_batt = not self.enable_random_low_batt

    def set_wizard_step(self, step: int):
        """Navigate to a specific wizard step."""
        self.wizard_step = step
        self.active_farm_source = "crop_image.png"
        self.update_background_image()
        self.update_step_tool_hint()

        step_titles = {
            1: "STEP 1: CROP FIELD SETUP & ALTITUDE CONFIGURATION",
            2: "STEP 2: MANUAL NODE PLACEMENT (3 TYPES & 3 SIZES)",
            3: "STEP 3: SQUARE SCANNING ZONES & CORRIDOR PLANNING",
            4: "STEP 4: FLEET SIZING (UP TO 10 DRONES) & BATTERY RESERVE",
            5: "STEP 5: STAGED SWARM SCANNING & HEATMAP GENERATION",
        }
        self.lbl_phase_badge.config(text=step_titles.get(step, ""))

        self.update_stepper_ui()
        self.build_step_controls()

        if step == 5 and self.mission_phase == 0:
            self.start_mission()

    def advance_step(self):
        """Advance to next step in the workflow."""
        if self.wizard_step < 5:
            self.set_wizard_step(self.wizard_step + 1)

    def retreat_step(self):
        """Return to previous step."""
        if self.wizard_step > 1:
            self.set_wizard_step(self.wizard_step - 1)

    def update_stepper_ui(self):
        """Update visual highlight on the top stepper buttons."""
        for idx, btn in enumerate(self.step_buttons):
            step_num = idx + 1
            if step_num == self.wizard_step:
                btn.config(bg="#0284c7", fg="#ffffff")
            elif step_num < self.wizard_step:
                btn.config(bg="#064e3b", fg="#34d399")
            else:
                btn.config(bg="#1e293b", fg="#64748b")

    def on_crop_changed(self, _=None):
        """Handle crop profile selection."""
        self.selected_crop_name = self.crop_combo.get()
        profile = CROP_PROFILES.get(self.selected_crop_name, {})
        self.scout_altitude_m = profile.get("alt_survey_m", 25.0)
        self.detail_altitude_m = profile.get("alt_detail_m", 12.0)
        self.generate_square_zones()
        self.generate_lawnmower_path()
        self.update_area_metrics()
        self.log_event(
            f"Selected crop: {self.selected_crop_name} (Row Spacing: {profile.get('row_spacing_m', 0.75)}m, Scout Alt: {self.scout_altitude_m}m).",
            category="GCS",
        )

    # -------------------------------------------------------------
    # Map Coordinates, Zoom, and Pan
    # -------------------------------------------------------------
    def metres_to_canvas(self, xm: float, ym: float) -> Tuple[float, float]:
        """Convert local Cartesian metres (0..100) to canvas screen pixels with zoom and pan."""
        pad = 32
        base_cx = (xm / self.field_w_m) * (self.canvas_w - 2 * pad) + pad
        base_cy = ((self.field_h_m - ym) / self.field_h_m) * (self.canvas_h - 2 * pad) + pad
        center_x = self.canvas_w / 2.0
        center_y = self.canvas_h / 2.0
        cx = center_x + (base_cx - center_x) * self.zoom_level + self.pan_x
        cy = center_y + (base_cy - center_y) * self.zoom_level + self.pan_y
        return cx, cy

    def canvas_to_metres(self, cx: float, cy: float) -> Tuple[float, float]:
        """Convert canvas screen pixels to local Cartesian metres (0..100) with zoom and pan."""
        pad = 32
        center_x = self.canvas_w / 2.0
        center_y = self.canvas_h / 2.0
        base_cx = (cx - self.pan_x - center_x) / self.zoom_level + center_x
        base_cy = (cy - self.pan_y - center_y) / self.zoom_level + center_y

        clamped_cx = max(pad, min(self.canvas_w - pad, base_cx))
        clamped_cy = max(pad, min(self.canvas_h - pad, base_cy))
        xm = ((clamped_cx - pad) / (self.canvas_w - 2 * pad)) * self.field_w_m
        ym = self.field_h_m - ((clamped_cy - pad) / (self.canvas_h - 2 * pad)) * self.field_h_m
        return round(xm, 1), round(ym, 1)

    def zoom_by(self, factor: float, cx: Optional[float] = None, cy: Optional[float] = None):
        """Zoom in or out smoothly, keeping the point under cursor stationary."""
        new_zoom = max(0.40, min(5.0, self.zoom_level * factor))
        if abs(new_zoom - self.zoom_level) < 1e-4:
            return

        if cx is None:
            cx = self.canvas_w / 2.0
        if cy is None:
            cy = self.canvas_h / 2.0

        center_x = self.canvas_w / 2.0
        center_y = self.canvas_h / 2.0

        self.pan_x = cx - center_x - ((cx - center_x - self.pan_x) / self.zoom_level) * new_zoom
        self.pan_y = cy - center_y - ((cy - center_y - self.pan_y) / self.zoom_level) * new_zoom
        self.zoom_level = new_zoom

        self.update_zoom_ui()
        self.update_background_image()

    def reset_zoom(self):
        """Reset map zoom to 100% and center the view."""
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update_zoom_ui()
        self.update_background_image()

    def fit_to_field(self):
        """Fit field boundary polygon to the canvas viewport."""
        if len(self.boundary_vertices) < 2:
            self.reset_zoom()
            return
        xs = [v[0] for v in self.boundary_vertices]
        ys = [v[1] for v in self.boundary_vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        bw_m = max(10.0, max_x - min_x)
        bh_m = max(10.0, max_y - min_y)

        avail_w = self.canvas_w - 140
        avail_h = self.canvas_h - 140

        pad = 32
        base_w = (bw_m / self.field_w_m) * (self.canvas_w - 2 * pad)
        base_h = (bh_m / self.field_h_m) * (self.canvas_h - 2 * pad)

        fit_zoom = min(avail_w / max(1.0, base_w), avail_h / max(1.0, base_h))
        self.zoom_level = max(0.5, min(4.0, fit_zoom))

        mid_xm = (min_x + max_x) / 2.0
        mid_ym = (min_y + max_y) / 2.0
        base_cx = (mid_xm / self.field_w_m) * (self.canvas_w - 2 * pad) + pad
        base_cy = ((self.field_h_m - mid_ym) / self.field_h_m) * (self.canvas_h - 2 * pad) + pad

        center_x = self.canvas_w / 2.0
        center_y = self.canvas_h / 2.0
        self.pan_x = -(base_cx - center_x) * self.zoom_level
        self.pan_y = -(base_cy - center_y) * self.zoom_level

        self.update_zoom_ui()
        self.update_background_image()

    def update_zoom_ui(self):
        """Update floating zoom label."""
        if hasattr(self, "lbl_zoom_val"):
            self.lbl_zoom_val.config(text=f"{int(self.zoom_level * 100)}%")

    def update_background_image(self):
        """Update resized background image corresponding to current zoom and pan."""
        raw = self.raw_farm_crop if self.active_farm_source == "crop_image.png" else None
        if not hasattr(self, "canvas") or not hasattr(self, "bg_img_item"):
            return

        if raw is None:
            self.canvas.itemconfig(self.bg_img_item, image="")
            return

        target_w = max(100, int(self.canvas_w * self.zoom_level))
        target_h = max(100, int(self.canvas_h * self.zoom_level))

        if (
            self.cached_bg_photo is None
            or self.cached_bg_size != (target_w, target_h)
            or self.cached_bg_source != self.active_farm_source
        ):
            try:
                resized = raw.resize((target_w, target_h), Image.Resampling.BILINEAR)
                self.cached_bg_photo = ImageTk.PhotoImage(resized)
                self.cached_bg_size = (target_w, target_h)
                self.cached_bg_source = self.active_farm_source
                self.canvas.itemconfig(self.bg_img_item, image=self.cached_bg_photo)
            except Exception as e:
                print(f"Error resizing background: {e}")
                return

        center_x = self.canvas_w / 2.0
        center_y = self.canvas_h / 2.0
        img_x = center_x - (target_w / 2.0) + self.pan_x
        img_y = center_y - (target_h / 2.0) + self.pan_y
        self.canvas.coords(self.bg_img_item, img_x, img_y)

    def on_mouse_wheel(self, event):
        """Handle mouse wheel scrolling to zoom smoothly centered at mouse cursor."""
        if event.delta > 0:
            self.zoom_by(1.15, event.x, event.y)
        elif event.delta < 0:
            self.zoom_by(1.0 / 1.15, event.x, event.y)

    def on_pan_start(self, event):
        """Start panning with mouse right-click or middle-click."""
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_pan_drag(self, event):
        """Update pan offset as mouse is dragged."""
        if self.is_panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.pan_x += dx
            self.pan_y += dy
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.update_background_image()

    def on_pan_end(self, _event):
        """End panning."""
        self.is_panning = False

    def on_mouse_move(self, event):
        """Update live cursor metric and GPS coordinates in the navigation box."""
        self.cursor_xm, self.cursor_ym = self.canvas_to_metres(event.x, event.y)
        self.cursor_lat, self.cursor_lon = metres_to_gps(self.cursor_xm, self.cursor_ym)
        if hasattr(self, "lbl_cursor_coords"):
            self.lbl_cursor_coords.config(
                text=f"Cursor: X: {self.cursor_xm:.1f}m, Y: {self.cursor_ym:.1f}m | GPS: {self.cursor_lat:.5f}°N, {self.cursor_lon:.5f}°E"
            )

    def on_canvas_configure(self, event):
        """Handle canvas resize when window is maximized or resized."""
        if event.width > 200 and event.height > 200:
            if abs(event.width - self.canvas_w) > 4 or abs(event.height - self.canvas_h) > 4:
                self.canvas_w = event.width
                self.canvas_h = event.height
                self.update_background_image()

    def on_canvas_left_click(self, event):
        """Handle left click: pan if in 'pan' mode, else interact with field."""
        if self.active_tool_mode == "pan":
            self.on_pan_start(event)
        else:
            self.on_canvas_click(event)

    def on_canvas_left_drag(self, event):
        """Handle left drag when in 'pan' mode."""
        if self.active_tool_mode == "pan":
            self.on_pan_drag(event)

    def on_canvas_left_release(self, event):
        """Handle left release when in 'pan' mode."""
        if self.active_tool_mode == "pan":
            self.on_pan_end(event)

    def on_canvas_click(self, event):
        """Handle interactive map clicks according to active step."""
        xm, ym = self.canvas_to_metres(event.x, event.y)
        xm = max(3.0, min(self.field_w_m - 3.0, xm))
        ym = max(3.0, min(self.field_h_m - 3.0, ym))

        # Step 1: Boundary Geofence Vertex Placement
        if self.wizard_step == 1:
            self.boundary_vertices.append((round(xm, 1), round(ym, 1)))
            self.generate_square_zones()
            self.generate_lawnmower_path()
            self.update_area_metrics()
            self.log_event(f"Boundary vertex V{len(self.boundary_vertices)} placed at ({xm:.1f}m, {ym:.1f}m).", category="GCS")

        # Step 2: Manual Node Placement (3 Types & 3 Sizes)
        elif self.wizard_step == 2:
            new_id = len(self.anomalies)
            node = FieldNode(
                new_id, self.active_place_node_type, round(xm, 1), round(ym, 1),
                size_key=self.active_place_node_size
            )
            self.anomalies.append(node)
            self.update_node_counts()
            self.log_event(
                f"Placed {node.type_info['badge']} ({node.size_info['label']} {node.radius_m:.0f}m) Node N{new_id} at ({xm:.1f}m, {ym:.1f}m).",
                category="ALERT",
            )

        # Step 3: Flight Path Waypoint Placement
        elif self.wizard_step == 3:
            self.lawnmower_waypoints.append((round(xm, 1), round(ym, 1)))
            self.update_area_metrics()
            self.log_event(f"Waypoint WP{len(self.lawnmower_waypoints)} placed at ({xm:.1f}m, {ym:.1f}m).", category="GCS")

    def remove_last_node(self):
        """Undo last placed node."""
        if self.anomalies:
            removed = self.anomalies.pop()
            self.update_node_counts()
            self.log_event(f"Removed node N{removed.id} ({removed.name}).", category="GCS")

    def clear_nodes(self):
        """Clear all placed nodes."""
        self.anomalies.clear()
        self.update_node_counts()
        self.log_event("All nodes cleared. Click on the crop field to place new nodes.", category="GCS")

    def update_node_counts(self):
        """Update node counters in the status ribbon."""
        y_cnt = sum(1 for a in self.anomalies if a.type_key == "yellowish")
        g_cnt = sum(1 for a in self.anomalies if a.type_key == "growth")
        d_cnt = sum(1 for a in self.anomalies if a.type_key == "disease")
        self.lbl_node_counts.config(
            text=f"Nodes Placed: {y_cnt} Yellowish 🟡 | {g_cnt} Brown 🟤 | {d_cnt} Disease 🔴 (Total: {len(self.anomalies)})"
        )

    def setup_default_nodes(self):
        """Populate initial set of 6 demo nodes with variable sizes."""
        self.anomalies = [
            FieldNode(0, "yellowish", 25.0, 25.0, size_key="small"),
            FieldNode(1, "disease", 75.0, 25.0, size_key="medium"),
            FieldNode(2, "growth", 35.0, 65.0, size_key="large"),
            FieldNode(3, "yellowish", 65.0, 50.0, size_key="medium"),
            FieldNode(4, "disease", 80.0, 80.0, size_key="large"),
            FieldNode(5, "growth", 25.0, 85.0, size_key="small"),
        ]
        self.update_node_counts()

    def clear_boundary(self):
        """Clear boundary vertices."""
        self.boundary_vertices = []
        self.square_zones = []
        self.lawnmower_waypoints = []
        self.update_area_metrics()
        self.log_event("Boundary vertices cleared.", category="GCS")

    def reset_default_boundary(self):
        """Reset boundary to standard 1 Ha rectangle."""
        self.boundary_vertices = [
            (10.0, 10.0),
            (10.0, 90.0),
            (90.0, 90.0),
            (90.0, 10.0),
        ]
        self.generate_square_zones()
        self.generate_lawnmower_path()
        self.update_area_metrics()
        self.log_event("Reset boundary to standard 1-Hectare polygon.", category="GCS")

    def clear_path(self):
        """Clear waypoints for manual planning."""
        self.lawnmower_waypoints = []
        self.current_wp_idx = 0
        self.update_area_metrics()
        self.log_event("Flight path cleared. Click on crop map to place waypoints manually.", category="GCS")

    def generate_lawnmower_path(self, spacing_m: Optional[float] = None):
        """Generate sweep corridors through the square scanning zones."""
        if len(self.boundary_vertices) < 3:
            return

        spacing = spacing_m if spacing_m is not None else self.active_zone_size_m

        xs = [v[0] for v in self.boundary_vertices]
        ys = [v[1] for v in self.boundary_vertices]
        x_min, x_max = min(xs) + 4.0, max(xs) - 4.0
        y_min, y_max = min(ys) + 4.0, max(ys) - 4.0

        if x_max <= x_min or y_max <= y_min:
            return

        num_lanes = max(3, int((y_max - y_min) / spacing) + 1)
        lane_gap = (y_max - y_min) / max(1, num_lanes - 1)

        self.lawnmower_waypoints = []
        for i in range(num_lanes):
            y_curr = y_min + i * lane_gap
            if i % 2 == 0:
                self.lawnmower_waypoints.append((round(x_min, 1), round(y_curr, 1)))
                self.lawnmower_waypoints.append((round(x_max, 1), round(y_curr, 1)))
            else:
                self.lawnmower_waypoints.append((round(x_max, 1), round(y_curr, 1)))
                self.lawnmower_waypoints.append((round(x_min, 1), round(y_curr, 1)))

        # Return to base at the end
        self.lawnmower_waypoints.append(self.base_m)
        self.update_area_metrics()

    def update_area_metrics(self):
        """Compute boundary area, perimeter, and optical footprint."""
        area_m2 = calculate_polygon_area(self.boundary_vertices)
        perim_m = calculate_polygon_perimeter(self.boundary_vertices)
        ha = area_m2 / 10000.0

        path_dist = 0.0
        for i in range(len(self.lawnmower_waypoints) - 1):
            p1, p2 = self.lawnmower_waypoints[i], self.lawnmower_waypoints[i + 1]
            path_dist += math.hypot(p2[0] - p1[0], p2[1] - p1[1])

        fw, fh = self.calculate_camera_footprint(self.scout_altitude_m)
        self.lbl_area_metric.config(
            text=f"Survey: {area_m2:,.0f} m² ({ha:.2f} Ha) | Alt: {self.scout_altitude_m:.1f}m | Footprint: {fw:.1f}m × {fh:.1f}m | Zones: {len(self.square_zones)} Squares"
        )

    def on_drone_count_changed(self):
        """Update swarm drone fleet count (1 to 9 swarm drones, up to 10 total)."""
        try:
            self.num_swarm_drones = max(1, min(9, int(self.spin_drones.get())))
            self.reset_simulation()
            self.log_event(f"Swarm Fleet updated: 1 Master Scout + {self.num_swarm_drones} Swarm Micro-Inspectors ({1 + self.num_swarm_drones} Total).", category="GCS")
        except Exception:
            pass

    def on_map_changed(self, _=None):
        """Switch active map background (Crop Photo or Plain Grid — Zero Satellite!)."""
        val = self.map_combo.get()
        if val == "Aerial Crop Photo":
            self.active_farm_source = "crop_image.png"
        else:
            self.active_farm_source = "plain"
        self.update_background_image()

    def on_speed_changed(self, _=None):
        """Update simulation speed."""
        val = self.speed_combo.get()
        self.sim_speed = float(val.replace("x", ""))
        self.log_event(f"Simulation speed: {self.sim_speed}x.", category="GCS")

    def toggle_play_pause(self):
        """Pause or play simulation."""
        self.is_running = not self.is_running
        if hasattr(self, "btn_play_pause"):
            self.btn_play_pause.config(text="Play" if not self.is_running else "Pause")

    def start_mission(self):
        """Begin active staged simulation."""
        if not self.lawnmower_waypoints:
            self.generate_lawnmower_path()

        if not self.anomalies:
            self.setup_default_nodes()

        self.reset_simulation()
        self.mission_phase = 1  # Stage A: Master Drone Scouting
        self.is_running = True
        if hasattr(self, "btn_play_pause"):
            self.btn_play_pause.config(text="Pause")

        self.master_drone.status = "SCANNING"
        self.current_wp_idx = 0
        if self.lawnmower_waypoints:
            self.master_drone.target_x, self.master_drone.target_y = self.lawnmower_waypoints[0]

        for d in self.swarm_drones:
            d.status = "STANDBY"

        self.log_event("=== MISSION LAUNCHED ===", category="GCS")
        self.log_comms("GCS", "D0", f"UPLOAD_MISSION_PLAN (Waypoints={len(self.lawnmower_waypoints)}, Alt={self.scout_altitude_m}m)")
        self.log_event(f"STAGE A: Master Drone D0 airborne. Scanning {len(self.square_zones)} square zones for Yellowish & Brown foliage candidates.", category="MASTER")
        self.log_event(f"Swarm Fleet ({self.num_swarm_drones} Drones) on STANDBY at Launchpad awaiting candidate identification.", category="SWARM")

    def reset_simulation(self):
        """Reset simulation states with optional low battery scenario."""
        self.sim_time = 0.0
        self.mission_phase = 0
        self.is_running = False
        self.covered_cells.clear()

        # Reset square zones
        for z in self.square_zones:
            z.status = "UNASSIGNED"
            z.assigned_drone_id = None
            z.coverage_pct = 0.0

        # Initialize Master Drone
        self.master_drone = VirtualUAV(0, True, self.base_m[0], self.base_m[1], altitude_m=self.scout_altitude_m, max_speed=7.2)

        # Initialize Swarm Drones (up to 9 micro-inspectors)
        self.swarm_drones = []
        for i in range(1, self.num_swarm_drones + 1):
            offset_x = self.base_m[0] + (3.4 * i)
            d = VirtualUAV(i, False, offset_x, self.base_m[1], altitude_m=self.detail_altitude_m, max_speed=9.0)
            d.status = "STANDBY"

            # Deterministic Low Battery Scenario
            if self.enable_random_low_batt and i in (1, 3):
                d.battery_eu = random.uniform(90.0, 130.0)  # ~18-26% battery
                self.log_event(f"SCENARIO SETUP: Drone D{d.id} initialized with LOW_BATTERY reserve ({d.battery_eu:.0f} Wh / {(d.battery_eu/500)*100:.0f}%).", category="ALERT")

            self.swarm_drones.append(d)

        self.current_wp_idx = 0
        if self.lawnmower_waypoints:
            self.master_drone.target_x, self.master_drone.target_y = self.lawnmower_waypoints[0]

        for a in self.anomalies:
            a.discovered = False
            a.is_candidate = False
            a.inspected = False
            a.assigned_drone_id = None
            a.rescan_progress = 0.0
            a.confirmed_disease_diagnosis = None

        self.update_labels()

    def inject_drone_failure(self):
        """Trigger motor fault on Swarm Drone 1 to demonstrate swarm self-healing."""
        if len(self.swarm_drones) > 0 and self.swarm_drones[0].status != "FAILED":
            d1 = self.swarm_drones[0]
            d1.status = "FAILED"
            self.log_event("FAULT INJECTION: Swarm Drone 1 suffered HARD_FAILURE!", category="FAULT")
            self.log_comms("D1", "GCS", "EMERGENCY_HALT (MOTOR_FAULT_DETECTED)")
            if d1.current_task_id is not None:
                task = next((a for a in self.anomalies if a.id == d1.current_task_id), None)
                if task:
                    task.assigned_drone_id = None
                    self.log_comms("GCS", "SWARM", f"TASK_REASSIGN (Zone=N{task.id})")
                    self.log_event(f"Node N{task.id} released. Reassigned to operational swarm drone!", category="SWARM")
                d1.current_task_id = None

    def log_event(self, msg: str, category: str = "GCS"):
        """Log event with aerospace badge tag."""
        self.event_text.config(state=tk.NORMAL)
        t_str = f"[{self.sim_time:05.1f}s] "
        badge = f" {category} "

        cat_tag = {
            "MASTER": "badge_master",
            "SWARM": "badge_swarm",
            "ALERT": "badge_alert",
            "COMMS": "badge_comms",
            "FAULT": "badge_fault",
            "GCS": "badge_gcs",
            "COLLISION": "badge_col",
        }.get(category, "badge_gcs")

        self.event_text.insert(tk.END, t_str, "time")
        self.event_text.insert(tk.END, badge, cat_tag)
        self.event_text.insert(tk.END, f" {msg}\n", "msg_text")
        self.event_text.see(tk.END)
        self.event_text.config(state=tk.DISABLED)

    def log_comms(self, source: str, dest: str, packet: str):
        """Log wireless mesh packet."""
        self.log_event(f"<{source} -> {dest}> {packet}", category="COMMS")

    def animation_tick(self):
        """60 FPS main animation tick."""
        dt = 0.016 * self.sim_speed

        self.comms_pulse = (self.comms_pulse + dt * 1.5) % 1.0
        self.radar_scan_angle = (self.radar_scan_angle + dt * 280.0) % 360.0
        self.radar_pulse_radius = (self.radar_pulse_radius + dt * 45.0) % 40.0

        # Radar cone sweep oscillation
        self.radar_sweep_cone += self.radar_sweep_dir * dt * 90.0
        if abs(self.radar_sweep_cone) > 35.0:
            self.radar_sweep_dir *= -1.0

        if self.is_running:
            self.update_simulation(dt)

        self.render_canvas()
        self.root.after(16, self.animation_tick)

    def get_drone_base_coords(self, drone: VirtualUAV) -> Tuple[float, float]:
        """Return base station launchpad coordinates for a given drone."""
        if drone.is_master:
            return self.base_m
        return (self.base_m[0] + (3.4 * drone.id), self.base_m[1])

    def calculate_mission_energy_cost(self, drone: VirtualUAV, target: FieldNode) -> Tuple[float, float, bool]:
        """
        Calculate flight distance, estimated energy (Wh), and return-to-base feasibility.
        Returns: (total_roundtrip_dist_m, est_energy_wh, is_feasible)
        """
        base_x, base_y = self.get_drone_base_coords(drone)
        d_out = math.hypot(drone.x - target.x, drone.y - target.y)
        d_home = math.hypot(target.x - base_x, target.y - base_y)
        total_dist_m = d_out + d_home

        # Realistic UAV Energy Model:
        # Cruising speed ~9.0 m/s @ 1.8 Wh/s => 0.15 Wh/m
        # Hover multispectral inspection: ~2.5s @ 1.8 Wh/s => 4.5 Wh
        # Safety reserve margin: 4.0 Wh
        est_energy_wh = (total_dist_m * 0.15) + 4.5 + 4.0
        reserve_limit_wh = 50.0  # 10% reserve of 500Wh capacity

        is_feasible = (drone.battery_eu - est_energy_wh) >= reserve_limit_wh
        return total_dist_m, est_energy_wh, is_feasible

    def allocate_tasks_battery_aware(self):
        """
        Optimal battery-aware shortest-path task allocation for collaborative multi-drone fleet.
        Drones concurrently select candidate anomaly zones based on minimum Euclidean distance
        and battery feasibility, ensuring safe return to base without mid-air depletion.
        """
        unassigned_candidates = [
            a for a in self.anomalies
            if a.is_candidate and not a.inspected and a.assigned_drone_id is None
        ]
        if not unassigned_candidates:
            return

        available_drones = [
            d for d in self.swarm_drones
            if d.status in ("IDLE", "STANDBY") and d.status != "FAILED"
        ]
        if not available_drones:
            return

        # Greedily match available drones to closest feasible candidate targets
        while available_drones and unassigned_candidates:
            best_pair = None
            best_score = float("inf")
            best_metrics = None

            for d in list(available_drones):
                # If drone battery is critically low (< 60 Wh / 12%), hold/return at launchpad
                if d.battery_eu < 60.0:
                    d.status = "LOW_BATTERY"
                    bx, by = self.get_drone_base_coords(d)
                    d.target_x, d.target_y = bx, by
                    available_drones.remove(d)
                    self.log_event(
                        f"SAFETY INTERVENTION: Drone D{d.id} reserve low ({d.battery_eu:.0f} Wh). Holding at Launchpad.",
                        category="ALERT",
                    )
                    continue

                for cand in unassigned_candidates:
                    tot_dist, est_wh, is_feasible = self.calculate_mission_energy_cost(d, cand)
                    if not is_feasible:
                        continue

                    dist_to_cand = math.hypot(d.x - cand.x, d.y - cand.y)
                    # Battery penalty factor: prioritize healthier drones and shortest travel path
                    batt_penalty = ((500.0 - d.battery_eu) / 500.0) * 8.0
                    score = dist_to_cand + (0.25 * tot_dist) + batt_penalty

                    if score < best_score:
                        best_score = score
                        best_pair = (d, cand)
                        best_metrics = (dist_to_cand, est_wh)

            if best_pair is None:
                break

            chosen_drone, chosen_cand = best_pair
            dist_to_cand, est_wh = best_metrics

            chosen_drone.current_task_id = chosen_cand.id
            chosen_cand.assigned_drone_id = chosen_drone.id
            chosen_drone.target_x = chosen_cand.x
            chosen_drone.target_y = chosen_cand.y
            chosen_drone.status = "TRAVELLING"

            available_drones.remove(chosen_drone)
            unassigned_candidates.remove(chosen_cand)

            self.log_event(
                f"Collaborative Dispatch: Drone D{chosen_drone.id} assigned shortest-path to Candidate N{chosen_cand.id} "
                f"(Dist: {dist_to_cand:.1f}m, Est: {est_wh:.0f}Wh, Battery: {chosen_drone.battery_eu:.0f}Wh).",
                category="SWARM",
            )
            self.log_comms("GCS", f"D{chosen_drone.id}", f"ASSIGN_OPTIMAL_PATH (Node=N{chosen_cand.id}, Dist={dist_to_cand:.1f}m)")

    def allocate_single_drone_next_task(self, drone: VirtualUAV):
        """Find the optimal shortest-path candidate for a drone finishing an inspection."""
        unassigned_candidates = [
            a for a in self.anomalies
            if a.is_candidate and not a.inspected and a.assigned_drone_id is None
        ]
        best_candidate = None
        best_score = float("inf")
        best_metrics = None

        if drone.battery_eu >= 60.0 and unassigned_candidates:
            for cand in unassigned_candidates:
                tot_dist, est_wh, is_feasible = self.calculate_mission_energy_cost(drone, cand)
                if not is_feasible:
                    continue
                dist_to_cand = math.hypot(drone.x - cand.x, drone.y - cand.y)
                score = dist_to_cand + (0.25 * tot_dist)
                if score < best_score:
                    best_score = score
                    best_candidate = cand
                    best_metrics = (dist_to_cand, est_wh)

        if best_candidate is not None:
            dist_to_cand, est_wh = best_metrics
            drone.current_task_id = best_candidate.id
            best_candidate.assigned_drone_id = drone.id
            drone.target_x = best_candidate.x
            drone.target_y = best_candidate.y
            drone.status = "TRAVELLING"
            self.log_event(
                f"Multi-Drone Retasked: Drone D{drone.id} -> Shortest-path Candidate N{best_candidate.id} "
                f"({dist_to_cand:.1f}m, Est: {est_wh:.0f}Wh).",
                category="SWARM",
            )
            self.log_comms("GCS", f"D{drone.id}", f"ENGAGE_NEXT (Node=N{best_candidate.id})")
        else:
            bx, by = self.get_drone_base_coords(drone)
            drone.target_x = bx
            drone.target_y = by
            drone.status = "RETURNING"
            self.log_event(f"Drone D{drone.id} completed inspections. Returning to Launchpad via shortest RTB path.", category="SWARM")
            self.log_comms(f"D{drone.id}", "GCS", "RTH_INITIATED")

    def check_collision_avoidance(self, drone: VirtualUAV, next_x: float, next_y: float) -> bool:
        """Check if moving to (next_x, next_y) maintains safe separation (>6.0m) to other drones."""
        safe_sep_m = 6.0
        all_drones = [self.master_drone] + self.swarm_drones

        for other in all_drones:
            if other.id == drone.id or other.status in ("STANDBY", "FAILED", "COMPLETED"):
                continue

            # Altitude clearance: Drones at distinct vertical layers (dz >= 5.0m) have clear 3D separation
            dz = abs(drone.altitude_m - other.altitude_m)
            if dz >= 5.0:
                continue

            dist = math.hypot(next_x - other.x, next_y - other.y)
            if dist < safe_sep_m:
                # Lower ID or Master has right-of-way
                if drone.id > other.id:
                    drone.holding_position = True
                    drone.holding_reason = f"Yielding to Drone D{other.id}"
                    return False  # Movement blocked to maintain safe separation

        drone.holding_position = False
        return True

    def update_simulation(self, dt: float):
        """Update kinematics, two-stage discovery, battery models, and collision avoidance."""
        self.sim_time += dt

        fw, fh = self.calculate_camera_footprint(self.scout_altitude_m)

        # -------------------------------------------------------------
        # STAGE A: Master Drone Scouting (Yellowish & Brown ONLY)
        # -------------------------------------------------------------
        if self.mission_phase >= 1:
            if self.master_drone.status in ("SCANNING", "RETURNING_BASE"):
                self.master_drone.battery_eu = max(0.0, self.master_drone.battery_eu - dt * 2.2)

                tx, ty = self.master_drone.target_x, self.master_drone.target_y
                dx = tx - self.master_drone.x
                dy = ty - self.master_drone.y
                dist = math.hypot(dx, dy)
                step_m = self.master_drone.max_speed * dt

                if dist > 1e-4:
                    self.master_drone.heading_deg = math.degrees(math.atan2(dx, dy))

                next_mx = self.master_drone.x + ((dx / dist) * step_m if dist > 0 else 0)
                next_my = self.master_drone.y + ((dy / dist) * step_m if dist > 0 else 0)

                # Collision check
                if self.check_collision_avoidance(self.master_drone, next_mx, next_my):
                    if step_m >= dist:
                        self.master_drone.x = tx
                        self.master_drone.y = ty
                        self.current_wp_idx += 1

                        if self.current_wp_idx < len(self.lawnmower_waypoints):
                            next_target = self.lawnmower_waypoints[self.current_wp_idx]
                            self.master_drone.target_x, self.master_drone.target_y = next_target
                            if next_target == self.base_m:
                                self.master_drone.status = "RETURNING_BASE"
                                self.log_event("Master Scout finished survey corridors! Returning to Base Station...", category="MASTER")
                        else:
                            # Stage A Completed
                            self.master_drone.status = "COMPLETED"
                            cand_count = sum(1 for a in self.anomalies if a.is_candidate)
                            self.log_event(f"Stage A Completed: Master Scout landed at Base. {cand_count} Candidate Anomaly Zones Flagged!", category="MASTER")
                            self.log_comms("D0", "GCS", f"SURVEY_REPORT (Candidates={cand_count})")
                            self.log_event(">>> ADVANCING TO STAGE B: MULTI-DRONE SWARM DEPLOYED FOR DETAILED INSPECTION <<<", category="SWARM")
                            if self.mission_phase == 1:
                                self.mission_phase = 2
                            for d in self.swarm_drones:
                                if d.status == "STANDBY":
                                    d.status = "IDLE"
                            # Immediately trigger collaborative multi-drone allocation so all drones launch together!
                            self.allocate_tasks_battery_aware()
                    else:
                        self.master_drone.x = next_mx
                        self.master_drone.y = next_my

                self.master_drone.trail.append((self.master_drone.x, self.master_drone.y))
                if len(self.master_drone.trail) > 200:
                    self.master_drone.trail.pop(0)

                # Record covered ground and update square zone statuses
                mx, my = self.master_drone.x, self.master_drone.y
                half_fw, half_fh = fw / 2.0, fh / 2.0
                int_mx, int_my = int(mx), int(my)

                for gx in range(max(0, int_mx - int(half_fw)), min(100, int_mx + int(half_fw))):
                    for gy in range(max(0, int_my - int(half_fh)), min(100, int_my + int(half_fh))):
                        self.covered_cells.add((gx, gy))

                # Update square zones
                for z in self.square_zones:
                    if z.x_min <= mx <= z.x_max and z.y_min <= my <= z.y_max:
                        z.status = "SCANNING"
                        z.assigned_drone_id = 0
                    elif z.status == "SCANNING" and math.hypot(mx - z.center_x, my - z.center_y) > half_fw:
                        z.status = "SCANNED"

                # STAGE A DISCOVERY RULE:
                # Master Drone at first detects YELLOWISH and BROWN ONLY!
                # Disease nodes are NOT detected as confirmed disease at this stage!
                for node in self.anomalies:
                    if not node.discovered:
                        dist_a = math.hypot(node.x - self.master_drone.x, node.y - self.master_drone.y)
                        if dist_a < (node.radius_m + half_fw * 0.7):
                            if node.type_info["is_scout_detectable"]:
                                # Yellowish or Brown node flagged as candidate!
                                node.discovered = True
                                node.is_candidate = True
                                self.log_event(
                                    f"Master Scout flagged {node.type_info['badge']} Candidate N{node.id} ({node.size_info['label']}) for detailed investigation.",
                                    category="ALERT",
                                )
                                self.log_comms("D0", "GCS", f"CANDIDATE_FLAGGED (id=N{node.id}, type={node.type_key})")
                            else:
                                # Disease node: Master scout detects only unclassified discoloration
                                node.discovered = True
                                node.is_candidate = True
                                self.log_event(
                                    f"Master Scout flagged Unclassified Discoloration at N{node.id} (Pending Swarm Micro-Inspection).",
                                    category="ALERT",
                                )

        # -------------------------------------------------------------
        # STAGE B: COLLABORATIVE MULTI-DRONE SWARM EXECUTION
        # Multiple drones actively working together simultaneously AFTER Master Drone completes!
        # Shortest-path routing based on battery feasibility & distance.
        # -------------------------------------------------------------
        if self.mission_phase == 2:
            # Dynamic multi-drone task allocator
            self.allocate_tasks_battery_aware()

            for drone in self.swarm_drones:
                if drone.status == "FAILED":
                    continue

                # Battery consumption
                if drone.status in ("TRAVELLING", "RETURNING", "INSPECTING", "LOW_BATTERY"):
                    drone.battery_eu = max(0.0, drone.battery_eu - dt * 1.8)

                    # Dynamic low battery check during flight
                    if drone.battery_eu < 90.0 and drone.status not in ("LOW_BATTERY", "RETURNING"):
                        drone.status = "LOW_BATTERY"
                        self.log_event(f"SAFETY INTERVENTION: Drone D{drone.id} hit reserve limit (18%). Releasing task and initiating RTH!", category="ALERT")
                        if drone.current_task_id is not None:
                            task = next((a for a in self.anomalies if a.id == drone.current_task_id), None)
                            if task:
                                task.assigned_drone_id = None
                            drone.current_task_id = None
                        bx, by = self.get_drone_base_coords(drone)
                        drone.target_x, drone.target_y = bx, by

                if drone.status in ("TRAVELLING", "RETURNING", "LOW_BATTERY"):
                    tx, ty = drone.target_x, drone.target_y
                    dx = tx - drone.x
                    dy = ty - drone.y
                    dist = math.hypot(dx, dy)
                    step_m = drone.max_speed * dt

                    if dist > 1e-4:
                        drone.heading_deg = math.degrees(math.atan2(dx, dy))

                    next_dx = drone.x + ((dx / dist) * step_m if dist > 0 else 0)
                    next_dy = drone.y + ((dy / dist) * step_m if dist > 0 else 0)

                    # COLLISION AVOIDANCE CHECK ("drone should not crash")
                    if self.check_collision_avoidance(drone, next_dx, next_dy):
                        if step_m >= dist:
                            drone.x = tx
                            drone.y = ty
                            if drone.status == "TRAVELLING":
                                drone.status = "INSPECTING"
                                task = next((a for a in self.anomalies if a.id == drone.current_task_id), None)
                                if task:
                                    self.update_evidence_panel(task, drone)
                                    self.log_event(f"Drone D{drone.id} hovering at Candidate N{task.id}: Multispectral optical sensor active.", category="SWARM")
                                    self.log_comms(f"D{drone.id}", "GCS", f"OPTICAL_SAMPLE_ACTIVE (Node=N{task.id})")
                            elif drone.status in ("RETURNING", "LOW_BATTERY"):
                                drone.status = "COMPLETED"
                                self.log_event(f"Drone D{drone.id} landed safely at Launchpad.", category="SWARM")
                                self.log_comms(f"D{drone.id}", "GCS", "LANDED_CONFIRMED")
                        else:
                            drone.x = next_dx
                            drone.y = next_dy

                    drone.trail.append((drone.x, drone.y))
                    if len(drone.trail) > 100:
                        drone.trail.pop(0)

                elif drone.status == "INSPECTING":
                    task = next((a for a in self.anomalies if a.id == drone.current_task_id), None)
                    if task:
                        task.rescan_progress += dt * 0.45
                        self.update_evidence_panel(task, drone)

                        if task.rescan_progress >= 1.0:
                            task.inspected = True
                            task.assigned_drone_id = None
                            drone.current_task_id = None

                            # STAGE B CLASSIFICATION RULE:
                            # Multi-drone inspection confirms the underlying pathology!
                            if task.type_key == "disease":
                                task.confirmed_disease_diagnosis = "Early / Late Fungal Blight (Alternaria Solani)"
                                self.log_event(
                                    f"DISEASE CONFIRMED: Drone D{drone.id} classified Node N{task.id} as {task.confirmed_disease_diagnosis} (Severity: 94%).",
                                    category="ALERT",
                                )
                            elif task.type_key == "yellowish":
                                task.confirmed_disease_diagnosis = "Nutrient Chlorosis (Nitrogen Deficiency)"
                                self.log_event(f"Drone D{drone.id} classified Node N{task.id} as {task.confirmed_disease_diagnosis}.", category="SWARM")
                            else:
                                task.confirmed_disease_diagnosis = "Viral Dwarfism & Canopy Stunting"
                                self.log_event(f"Drone D{drone.id} classified Node N{task.id} as {task.confirmed_disease_diagnosis}.", category="SWARM")

                            self.log_comms(f"D{drone.id}", "GCS", f"EVIDENCE_VERIFIED (Node=N{task.id}, Diagnosis={task.confirmed_disease_diagnosis})")

                            # Look for next uninspected candidate using battery-aware shortest-path!
                            self.allocate_single_drone_next_task(drone)

            # Check mission completion
            all_done = len(self.anomalies) > 0 and all(a.inspected for a in self.anomalies if a.is_candidate)
            all_landed = all(d.status in ("COMPLETED", "FAILED") for d in self.swarm_drones)
            master_done = self.master_drone.status in ("COMPLETED", "STANDBY")
            if all_done and all_landed and master_done and self.mission_phase in (1, 2):
                self.mission_phase = 3
                self.log_event("MISSION ACCOMPLISHED: All candidate zones inspected and classified by Swarm fleet!", category="GCS")
                self.log_comms("GCS", "FLEET", "MISSION_SUCCESS_ALL_TARGETS_CLASSIFIED")

        self.update_labels()

    def update_labels(self):
        """Update telemetry cards, battery gauges, and fleet status."""
        self.lbl_clock.config(text=f"Mission Clock: {self.sim_time:.1f} s")

        m_lat, m_lon = metres_to_gps(self.master_drone.x, self.master_drone.y)
        self.lbl_master_status.config(
            text=f"Master Drone (D0): {self.master_drone.status} | GPS: {m_lat:.5f}°N, {m_lon:.5f}°E"
        )

        # Master Drone Battery Bar
        m_batt = max(0.0, min(100.0, (self.master_drone.battery_eu / 500.0) * 100.0))
        m_bars = int(m_batt / 10)
        m_bar_str = "█" * m_bars + "░" * (10 - m_bars)
        m_spd = 7.2 if self.master_drone.status in ("SCANNING", "RETURNING_BASE") else 0.0
        self.lbl_master_battery.config(
            text=f"Battery: [{m_bar_str}] {m_batt:.0f}% ({self.master_drone.battery_eu:.0f} Wh) | Alt: {self.scout_altitude_m:.1f}m | Spd: {m_spd:.1f} m/s"
        )

        # Swarm Fleet Status
        active_count = sum(1 for d in self.swarm_drones if d.status in ("TRAVELLING", "INSPECTING", "RETURNING"))
        if self.mission_phase == 1:
            self.lbl_swarm_status.config(
                text=f"Swarm Fleet ({self.num_swarm_drones} Drones): STANDBY AT LAUNCHPAD (Awaiting Master Scout Completion)"
            )
        elif self.mission_phase == 2:
            self.lbl_swarm_status.config(
                text=f"Swarm Fleet ({self.num_swarm_drones} Drones): {active_count} AIRBORNE | Collaborative Shortest-Path Inspection Active"
            )
        elif self.mission_phase == 3:
            self.lbl_swarm_status.config(
                text=f"Swarm Fleet ({self.num_swarm_drones} Drones): MISSION COMPLETE | All Candidates Inspected & Safely Landed"
            )
        else:
            self.lbl_swarm_status.config(
                text=f"Swarm Fleet ({self.num_swarm_drones} Drones): STANDBY AT LAUNCHPAD"
            )
        s_details = []
        for d in self.swarm_drones:
            b = max(0.0, min(100.0, (d.battery_eu / 500.0) * 100.0))
            b_bars = int(b / 10)
            b_str = "█" * b_bars + "░" * (10 - b_bars)
            target_info = f"➔ N{d.current_task_id}" if d.current_task_id is not None else ""
            s_details.append(f"D{d.id}: [{b_str}] {b:.0f}% ({d.status}{' ' + target_info if target_info else ''})")
        self.lbl_swarm_details.config(text=" | ".join(s_details[:5]) + ("..." if len(s_details) > 5 else ""))

        self.update_node_counts()

    def update_evidence_panel(self, node: FieldNode, drone: VirtualUAV):
        """Display photographic evidence corresponding to node type and disease diagnosis."""
        img_tk = self.evidence_photos.get(node.file)
        if img_tk:
            self.lbl_evidence_img.config(image=img_tk, width=240, height=150)
            self.lbl_evidence_img.image = img_tk

        stage_title = f"Node N{node.id} — {node.name}"
        if node.confirmed_disease_diagnosis:
            stage_title += f" [{node.confirmed_disease_diagnosis}]"

        self.lbl_evidence_title.config(text=stage_title, fg=node.color)

        # Dynamic severity bar
        sev_bars = int(node.severity * 10)
        sev_str = "█" * sev_bars + "░" * (10 - sev_bars)
        self.lbl_evidence_severity.config(
            text=f"Severity Meter: [{sev_str}] {node.severity * 100:.1f}% Confidence",
            fg=node.color,
        )

        rescan_pct = min(100.0, node.rescan_progress * 100.0)
        diag = node.confirmed_disease_diagnosis or "Under Multispectral Analysis..."

        self.lbl_evidence_details.config(
            text=(
                f"• Anomaly Extent: {node.size_info['label']} (Radius: {node.radius_m:.0f}m)\n"
                f"• GPS Location: ({node.gps_lat:.5f}°N, {node.gps_lon:.5f}°E)\n"
                f"• Optical Rescan: {rescan_pct:.0f}% (Stage B Detail Alt: {self.detail_altitude_m:.1f}m)\n"
                f"• Investigating UAV: Swarm Drone D{drone.id}\n"
                f"• Verified Pathology: {diag}\n"
                f"• Agronomic Action: Targeted Variable-Rate Fungicide / Nutrient Application"
            )
        )

    def render_map_scale(self):
        """Draw dynamic GCS / GIS dual-tone scale bar in bottom-left corner of canvas."""
        pad = 32
        px_per_m = ((self.canvas_w - 2 * pad) / self.field_w_m) * self.zoom_level

        candidates = [1, 2, 5, 10, 20, 25, 50, 100]
        chosen_m = 10
        for m in candidates:
            bar_px = m * px_per_m
            if bar_px >= 75:
                chosen_m = m
                break
        else:
            chosen_m = candidates[-1]

        bar_w = chosen_m * px_per_m
        half_w = bar_w / 2.0
        half_m = chosen_m / 2.0

        sx = 20
        sy = self.canvas_h - 38
        box_w = max(210, int(bar_w + 32))
        box_h = 32

        self.canvas.create_rectangle(
            sx - 8, sy - 14, sx - 8 + box_w, sy - 14 + box_h,
            fill="#050811", outline="#334155", width=1, tags="dynamic"
        )

        # Alternating scale segments
        self.canvas.create_rectangle(sx, sy, sx + half_w, sy + 5, fill="#38bdf8", outline="#ffffff", width=1, tags="dynamic")
        self.canvas.create_rectangle(sx + half_w, sy, sx + bar_w, sy + 5, fill="#0c4a6e", outline="#ffffff", width=1, tags="dynamic")

        # Tick marks
        self.canvas.create_line(sx, sy - 4, sx, sy + 8, fill="#ffffff", width=1.5, tags="dynamic")
        self.canvas.create_line(sx + half_w, sy - 4, sx + half_w, sy + 8, fill="#ffffff", width=1.5, tags="dynamic")
        self.canvas.create_line(sx + bar_w, sy - 4, sx + bar_w, sy + 8, fill="#ffffff", width=1.5, tags="dynamic")

        self.canvas.create_text(sx, sy - 8, text="0", fill="#f8fafc", font=("Consolas", 7, "bold"), anchor=tk.S, tags="dynamic")
        half_txt = f"{int(half_m)}" if half_m.is_integer() else f"{half_m:.1f}"
        self.canvas.create_text(sx + half_w, sy - 8, text=f"{half_txt}m", fill="#f8fafc", font=("Consolas", 7, "bold"), anchor=tk.S, tags="dynamic")
        self.canvas.create_text(sx + bar_w, sy - 8, text=f"{chosen_m}m", fill="#38bdf8", font=("Consolas", 7, "bold"), anchor=tk.S, tags="dynamic")

        m_per_px = 1.0 / max(1e-4, px_per_m)
        info_txt = f"Scale: 1px = {m_per_px * 100:.1f}cm | Zoom: {int(self.zoom_level * 100)}%"
        self.canvas.create_text(sx + bar_w + 10, sy + 2, text=info_txt, fill="#94a3b8", font=("Consolas", 7), anchor=tk.W, tags="dynamic")

    def render_drone_footprint_coverage(self):
        """Render the camera optical footprint and ground area coverage dynamically on screen."""
        fw_m, fh_m = self.calculate_camera_footprint(self.scout_altitude_m)
        fw_px = (fw_m / self.field_w_m) * (self.canvas_w - 64) * self.zoom_level
        fh_px = (fh_m / self.field_h_m) * (self.canvas_h - 64) * self.zoom_level
        cov_area_m2 = fw_m * fh_m

        # Position of footprint:
        # In Step 1: Center of field (50m, 50m) so it is prominently displayed while adjusting height!
        # In Steps 2-5: Center on Master Drone position
        if self.wizard_step == 1:
            fx, fy = self.metres_to_canvas(50.0, 50.0)
            is_preview = True
        else:
            fx, fy = self.metres_to_canvas(self.master_drone.x, self.master_drone.y)
            is_preview = False

        half_w = fw_px / 2.0
        half_h = fh_px / 2.0
        x1, y1 = fx - half_w, fy - half_h
        x2, y2 = fx + half_w, fy + half_h

        # 1. Optical Footprint Coverage Rectangle
        outline_col = "#38bdf8" if is_preview else "#0ea5e9"
        line_w = 2 if is_preview else 1.5
        self.canvas.create_rectangle(
            x1, y1, x2, y2, outline=outline_col, width=line_w, dash=(4, 4), tags="dynamic"
        )

        # 2. Viewfinder Optical Corner Brackets (Camera sensor style)
        cl = max(8, min(24, int(min(half_w, half_h) * 0.4)))
        # Top-Left
        self.canvas.create_line(x1, y1 + cl, x1, y1, x1 + cl, y1, fill="#0284c7", width=3, tags="dynamic")
        # Top-Right
        self.canvas.create_line(x2 - cl, y1, x2, y1, x2, y1 + cl, fill="#0284c7", width=3, tags="dynamic")
        # Bottom-Left
        self.canvas.create_line(x1, y2 - cl, x1, y2, x1 + cl, y2, fill="#0284c7", width=3, tags="dynamic")
        # Bottom-Right
        self.canvas.create_line(x2 - cl, y2, x2, y2, x2, y2 - cl, fill="#0284c7", width=3, tags="dynamic")

        # 3. Dimension Indicators & Real-Time Area Badge
        if is_preview or self.zoom_level >= 0.75:
            # Top width dimension line & label
            self.canvas.create_line(x1, y1 - 8, x2, y1 - 8, fill="#38bdf8", width=1.5, arrow=tk.BOTH, tags="dynamic")
            self.canvas.create_text(fx, y1 - 18, text=f"↔ Optical Swath Width: {fw_m:.1f} m", fill="#38bdf8", font=("Consolas", 8, "bold"), tags="dynamic")

            # Left height dimension line & label
            self.canvas.create_line(x1 - 8, y1, x1 - 8, y2, fill="#38bdf8", width=1.5, arrow=tk.BOTH, tags="dynamic")
            self.canvas.create_text(x1 - 14, fy, text=f"↕ {fh_m:.1f}m", fill="#38bdf8", font=("Consolas", 8, "bold"), anchor=tk.E, tags="dynamic")

            # Center Area Coverage Badge
            badge_txt = f"📷 Drone Coverage Area: {cov_area_m2:.0f} m² ({fw_m:.1f}m × {fh_m:.1f}m at {self.scout_altitude_m:.1f}m Alt)"
            if is_preview:
                badge_txt += " [LIVE PREVIEW]"
            bw = min(170, max(120, int(len(badge_txt) * 3.8)))
            self.canvas.create_rectangle(fx - bw, fy - 11, fx + bw, fy + 11, fill="#090d16", outline="#0284c7", width=1, tags="dynamic")
            self.canvas.create_text(fx, fy, text=badge_txt, fill="#f8fafc", font=("Segoe UI", 7, "bold"), tags="dynamic")

    def render_compass_rose(self):
        """Draw authentic aviation compass rose at bottom-right of map."""
        cx = self.canvas_w - 55
        cy = self.canvas_h - 60

        self.canvas.create_oval(cx - 28, cy - 28, cx + 28, cy + 28, fill="#050811", outline="#38bdf8", width=1.5, tags="dynamic")
        self.canvas.create_oval(cx - 23, cy - 23, cx + 23, cy + 23, outline="#334155", width=1, dash=(2, 2), tags="dynamic")

        self.canvas.create_line(cx, cy - 26, cx, cy + 26, fill="#334155", width=1, tags="dynamic")
        self.canvas.create_line(cx - 26, cy, cx + 26, cy, fill="#334155", width=1, tags="dynamic")

        self.canvas.create_polygon([cx, cy - 22, cx - 6, cy - 4, cx + 6, cy - 4], fill="#f43f5e", outline="#ffffff", width=1, tags="dynamic")
        self.canvas.create_polygon([cx, cy + 22, cx - 6, cy + 4, cx + 6, cy + 4], fill="#475569", outline="#cbd5e1", width=1, tags="dynamic")

        self.canvas.create_text(cx, cy - 14, text="N", fill="#ffffff", font=("Segoe UI", 7, "bold"), tags="dynamic")
        self.canvas.create_text(cx, cy + 14, text="S", fill="#94a3b8", font=("Segoe UI", 6), tags="dynamic")
        self.canvas.create_text(cx + 17, cy, text="E", fill="#94a3b8", font=("Segoe UI", 6), tags="dynamic")
        self.canvas.create_text(cx - 17, cy, text="W", fill="#94a3b8", font=("Segoe UI", 6), tags="dynamic")

        hdg = int(self.master_drone.heading_deg) % 360
        self.canvas.create_text(cx, cy + 34, text=f"HDG: {hdg:03d}°", fill="#38bdf8", font=("Consolas", 7, "bold"), tags="dynamic")

    def render_canvas(self):
        """Flicker-free canvas render loop with smooth heatmap, square zones, and radar effects."""
        self.canvas.delete("dynamic")

        # 1. Plain grid fallback if selected
        if self.active_farm_source == "plain":
            p_tl_x, p_tl_y = self.metres_to_canvas(0.0, self.field_h_m)
            p_br_x, p_br_y = self.metres_to_canvas(self.field_w_m, 0.0)
            self.canvas.create_rectangle(p_tl_x, p_tl_y, p_br_x, p_br_y, fill="#064e3b", outline="#047857", width=2, tags="dynamic")
            for grid_m in range(0, int(self.field_w_m) + 1, 10):
                lx1, ly1 = self.metres_to_canvas(grid_m, 0.0)
                lx2, ly2 = self.metres_to_canvas(grid_m, self.field_h_m)
                self.canvas.create_line(lx1, ly1, lx2, ly2, fill="#047857", dash=(2, 4), tags="dynamic")
                my1, mx1 = self.metres_to_canvas(0.0, grid_m)
                my2, mx2 = self.metres_to_canvas(self.field_w_m, grid_m)
                self.canvas.create_line(my1, mx1, my2, mx2, fill="#047857", dash=(2, 4), tags="dynamic")

        # 2. MULTIPLE SQUARE SCANNING ZONES IN FARM AREA
        # As requested: "make multiple zones squares in farm area made inside that only at each zone the drone will go"
        if len(self.square_zones) > 0 and self.wizard_step in (1, 3, 4, 5):
            for z in self.square_zones:
                zx1, zy1 = self.metres_to_canvas(z.x_min, z.y_max)
                zx2, zy2 = self.metres_to_canvas(z.x_max, z.y_min)

                if z.status == "SCANNING":
                    z_outline = "#38bdf8"
                    z_w = 2
                    # Active animated scanning highlight
                    self.canvas.create_rectangle(zx1, zy1, zx2, zy2, outline=z_outline, width=z_w, tags="dynamic")
                elif z.status == "SCANNED":
                    z_outline = "#059669"
                    z_w = 1
                    self.canvas.create_rectangle(zx1, zy1, zx2, zy2, outline=z_outline, width=z_w, dash=(3, 3), tags="dynamic")
                else:
                    z_outline = "#334155"
                    z_w = 1
                    self.canvas.create_rectangle(zx1, zy1, zx2, zy2, outline=z_outline, width=z_w, dash=(2, 4), tags="dynamic")

                # Zone ID tag
                cx, cy = self.metres_to_canvas(z.center_x, z.center_y)
                if self.zoom_level >= 0.8:
                    lbl_color = "#38bdf8" if z.status == "SCANNING" else ("#34d399" if z.status == "SCANNED" else "#64748b")
                    self.canvas.create_text(cx, cy, text=f"Z{z.id}", fill=lbl_color, font=("Consolas", 7), tags="dynamic")

        # 3. PROPER DUAL-TONE AGRICULTURAL VEGETATION STRESS HEATMAP (GREENERY & YELLOWISH)
        # As requested: "make proepr yellow heatmap too... in heatmpa greenery and yellowish only has to show"
        # Continuous non-pixelated coverage: Smooth scanned canopy green + glowing golden-yellow chlorosis stress fields
        if self.wizard_step == 5 and self.heatmap_enabled and len(self.covered_cells) > 0:
            # 3A. Draw smooth, seamless agricultural green coverage across surveyed territory
            step = 2
            cell_coords = list(self.covered_cells)
            disc_r = max(4, int(7 * self.zoom_level))
            for gx, gy in cell_coords[::step]:
                cx, cy = self.metres_to_canvas(gx, gy)
                # Soft translucent lush canopy green (#15803d)
                self.canvas.create_oval(
                    cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r,
                    fill="#15803d", outline="", tags="dynamic"
                )

            # 3B. Draw connecting chlorosis stress corridors between nearby anomalies (< 32m)
            active_anomalies = [a for a in self.anomalies if (a.discovered or a.is_candidate)]
            for i in range(len(active_anomalies)):
                for j in range(i + 1, len(active_anomalies)):
                    a1 = active_anomalies[i]
                    a2 = active_anomalies[j]
                    dist_nodes = math.hypot(a1.x - a2.x, a1.y - a2.y)
                    if dist_nodes <= 32.0:
                        p1x, p1y = self.metres_to_canvas(a1.x, a1.y)
                        p2x, p2y = self.metres_to_canvas(a2.x, a2.y)
                        band_w = max(6, int(12 * self.zoom_level))
                        self.canvas.create_line(p1x, p1y, p2x, p2y, fill="#fde047", width=band_w, capstyle=tk.ROUND, tags="dynamic")
                        self.canvas.create_line(p1x, p1y, p2x, p2y, fill="#facc15", width=max(2, band_w - 4), capstyle=tk.ROUND, tags="dynamic")

            # 3C. Render ultra-smooth multi-stop golden-yellow chlorosis stress hotspots
            for a in active_anomalies:
                ax, ay = self.metres_to_canvas(a.x, a.y)
                rad_px = (a.radius_m / self.field_w_m) * (self.canvas_w - 64) * self.zoom_level

                # Ring 1: Outer transitional lime/chartreuse halo (blends with crop greenery)
                r1 = rad_px * 1.35
                self.canvas.create_oval(
                    ax - r1, ay - r1, ax + r1, ay + r1,
                    outline="#a3e635", width=max(1, int(2 * self.zoom_level)), dash=(3, 3), tags="dynamic"
                )

                # Ring 2: Sunny yellow outer chlorosis halo
                r2 = rad_px * 1.10
                self.canvas.create_oval(
                    ax - r2, ay - r2, ax + r2, ay + r2,
                    fill="#fef08a", outline="#facc15", width=1, tags="dynamic"
                )

                # Ring 3: Vibrant agricultural golden-yellow core stress field
                r3 = rad_px * 0.82
                self.canvas.create_oval(
                    ax - r3, ay - r3, ax + r3, ay + r3,
                    fill="#facc15", outline="#eab308", width=1, tags="dynamic"
                )

                # Ring 4: Deep amber-gold physiological stress buffer
                r4 = rad_px * 0.55
                mid_col = "#eab308" if a.type_key == "yellowish" else ("#d97706" if a.type_key == "growth" else "#f97316")
                self.canvas.create_oval(
                    ax - r4, ay - r4, ax + r4, ay + r4,
                    fill=mid_col, outline="", tags="dynamic"
                )

                # Ring 5: Pathological epicenter
                r5 = max(5, rad_px * 0.32)
                core_col = "#dc2626" if a.type_key == "disease" else ("#ca8a04" if a.type_key == "yellowish" else "#92400e")
                self.canvas.create_oval(
                    ax - r5, ay - r5, ax + r5, ay + r5,
                    fill=core_col, outline="#ffffff", width=max(1, int(1.5 * self.zoom_level)), tags="dynamic"
                )

                # Reflective center highlight
                r6 = max(2, int(r5 * 0.35))
                center_dot_col = "#ffffff" if a.type_key == "disease" else "#fef08a"
                self.canvas.create_oval(
                    ax - r6, ay - r6, ax + r6, ay + r6,
                    fill=center_dot_col, outline="", tags="dynamic"
                )

            # 3D. On-Screen NDVI Vegetation Stress Heatmap HUD Legend
            leg_x = self.canvas_w - 410
            leg_y = 14
            self.canvas.create_rectangle(leg_x, leg_y, leg_x + 396, leg_y + 44, fill="#090d16", outline="#34d399", width=1, tags="dynamic")
            self.canvas.create_text(leg_x + 8, leg_y + 11, text="🌿 NDVI VEGETATION STRESS HEATMAP", fill="#34d399", font=("Segoe UI", 7, "bold"), anchor=tk.W, tags="dynamic")
            self.canvas.create_oval(leg_x + 8, leg_y + 24, leg_x + 18, leg_y + 34, fill="#15803d", outline="", tags="dynamic")
            self.canvas.create_text(leg_x + 22, leg_y + 29, text="Healthy", fill="#86efac", font=("Segoe UI", 7), anchor=tk.W, tags="dynamic")
            self.canvas.create_oval(leg_x + 78, leg_y + 24, leg_x + 88, leg_y + 34, fill="#facc15", outline="", tags="dynamic")
            self.canvas.create_text(leg_x + 92, leg_y + 29, text="Chlorosis (Yellow)", fill="#fde047", font=("Segoe UI", 7), anchor=tk.W, tags="dynamic")
            self.canvas.create_oval(leg_x + 198, leg_y + 24, leg_x + 208, leg_y + 34, fill="#d97706", outline="", tags="dynamic")
            self.canvas.create_text(leg_x + 212, leg_y + 29, text="Stunted", fill="#fdba74", font=("Segoe UI", 7), anchor=tk.W, tags="dynamic")
            self.canvas.create_oval(leg_x + 276, leg_y + 24, leg_x + 286, leg_y + 34, fill="#dc2626", outline="", tags="dynamic")
            self.canvas.create_text(leg_x + 290, leg_y + 29, text="Blight Core", fill="#fca5a5", font=("Segoe UI", 7), anchor=tk.W, tags="dynamic")

        # 4. Geofence Boundary Polygon
        if len(self.boundary_vertices) >= 2:
            poly_pts = [self.metres_to_canvas(x, y) for (x, y) in self.boundary_vertices]
            poly_flat = [coord for pt in poly_pts for coord in pt]

            if len(self.boundary_vertices) >= 3:
                self.canvas.create_polygon(poly_flat, fill="", outline="#10b981", width=max(2, int(3 * math.sqrt(self.zoom_level))), tags="dynamic")

            for i in range(len(poly_pts) - 1):
                p1, p2 = poly_pts[i], poly_pts[i + 1]
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#34d399", width=max(1, int(2 * math.sqrt(self.zoom_level))), tags="dynamic")

            for i, (vx, vy) in enumerate(self.boundary_vertices):
                cx, cy = self.metres_to_canvas(vx, vy)
                v_lat, v_lon = metres_to_gps(vx, vy)
                vr = max(4, int(5 * math.sqrt(self.zoom_level)))
                self.canvas.create_oval(cx - vr, cy - vr, cx + vr, cy + vr, fill="#0284c7", outline="#ffffff", width=2, tags="dynamic")
                self.canvas.create_text(
                    cx + 8, cy - 8,
                    text=f"V{i+1}: {v_lat:.5f}°N, {v_lon:.5f}°E",
                    fill="#f8fafc", font=("Consolas", 7, "bold"), anchor=tk.W, tags="dynamic"
                )

        # 5. Master Drone Flight Path Corridors (High-Visibility GCS Styling)
        if len(self.lawnmower_waypoints) >= 2 and self.wizard_step in (3, 4, 5):
            pts = [self.metres_to_canvas(x, y) for (x, y) in self.lawnmower_waypoints]
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i + 1]
                if i < self.current_wp_idx - 1:
                    # Completed survey legs (Emerald Green)
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#059669", width=2, tags="dynamic")
                elif i == self.current_wp_idx - 1 or (i == 0 and self.current_wp_idx == 0):
                    # Active flight leg (Glowing Electric Sky-Blue Corridor with Directional Arrow)
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#0369a1", width=5, tags="dynamic")
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#38bdf8", width=2.5, dash=(6, 3), arrow=tk.LAST, tags="dynamic")
                else:
                    # Upcoming planned legs (Clean Slate Corridor)
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#475569", dash=(3, 3), width=1, tags="dynamic")

            for i, (wx, wy) in enumerate(self.lawnmower_waypoints):
                cx, cy = self.metres_to_canvas(wx, wy)
                wpr = max(3, int(4 * math.sqrt(self.zoom_level)))
                if i < self.current_wp_idx:
                    # Completed waypoint
                    self.canvas.create_oval(cx - wpr, cy - wpr, cx + wpr, cy + wpr, fill="#10b981", outline="#ffffff", width=1, tags="dynamic")
                elif i == self.current_wp_idx:
                    # Active target waypoint (Pulsing Cyan Ring)
                    pulse_r = wpr + 4 + int(math.sin(self.sim_time * 6.0) * 2)
                    self.canvas.create_oval(cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r, outline="#38bdf8", width=2, tags="dynamic")
                    self.canvas.create_oval(cx - wpr, cy - wpr, cx + wpr, cy + wpr, fill="#38bdf8", outline="#ffffff", width=2, tags="dynamic")
                    self.canvas.create_text(cx, cy - 12, text=f"WP{i+1} [TARGET]", fill="#38bdf8", font=("Consolas", 7, "bold"), tags="dynamic")
                else:
                    # Future waypoint
                    self.canvas.create_oval(cx - wpr, cy - wpr, cx + wpr, cy + wpr, fill="#334155", outline="#64748b", tags="dynamic")
                    if i < 8 or i % 3 == 0:
                        self.canvas.create_text(cx, cy - 10, text=f"WP{i+1}", fill="#94a3b8", font=("Consolas", 6), tags="dynamic")

        # 6. Base Station Launchpad
        bx, by = self.metres_to_canvas(self.base_m[0], self.base_m[1])
        base_r = max(14, int(20 * math.sqrt(self.zoom_level)))
        self.canvas.create_oval(bx - base_r, by - base_r, bx + base_r, by + base_r, fill="#090d16", outline="#f59e0b", width=2, tags="dynamic")
        self.canvas.create_text(bx, by, text="GCS", fill="#f59e0b", font=("Segoe UI", 9, "bold"), tags="dynamic")
        self.canvas.create_text(
            bx + base_r + 6, by,
            text=f"Base Station Launchpad\n({ORIGIN_LAT:.5f}°N, {ORIGIN_LON:.5f}°E)",
            fill="#f8fafc", font=("Segoe UI", 8, "bold"), anchor=tk.W, tags="dynamic"
        )

        # 7. Manually Placed Nodes (Yellowish 🟡, Brown 🟤, Disease 🔴) with Size Ring & Drone Lock
        for a in self.anomalies:
            ax, ay = self.metres_to_canvas(a.x, a.y)
            nr = max(10, min(36, int(13 * math.sqrt(self.zoom_level))))
            rad_px = (a.radius_m / self.field_w_m) * (self.canvas_w - 64) * self.zoom_level

            # Outer extent boundary representing configured Small/Medium/Large size
            self.canvas.create_oval(ax - rad_px, ay - rad_px, ax + rad_px, ay + rad_px, outline=a.color, width=1, dash=(3, 3), tags="dynamic")

            # Target Lock Reticle if assigned to an active swarm drone
            if a.assigned_drone_id is not None and not a.inspected:
                assigned_d = next((d for d in self.swarm_drones if d.id == a.assigned_drone_id), None)
                if assigned_d:
                    d_col = FLEET_COLORS[(assigned_d.id) % len(FLEET_COLORS)]
                    br = nr + 7
                    # Corner tracking brackets
                    self.canvas.create_line(ax - br, ay - br + 5, ax - br, ay - br, ax - br + 5, ay - br, fill=d_col, width=2, tags="dynamic")
                    self.canvas.create_line(ax + br - 5, ay - br, ax + br, ay - br, ax + br, ay - br + 5, fill=d_col, width=2, tags="dynamic")
                    self.canvas.create_line(ax - br, ay + br - 5, ax - br, ay + br, ax - br + 5, ay + br, fill=d_col, width=2, tags="dynamic")
                    self.canvas.create_line(ax + br - 5, ay + br, ax + br, ay + br, ax + br, ay + br - 5, fill=d_col, width=2, tags="dynamic")
                    self.canvas.create_text(ax, ay - br - 8, text=f"LOCK: D{assigned_d.id}", fill=d_col, font=("Segoe UI", 7, "bold"), tags="dynamic")

            if a.inspected:
                # Stage B confirmed
                self.canvas.create_oval(ax - nr, ay - nr, ax + nr, ay + nr, fill="#059669", outline="#ffffff", width=2, tags="dynamic")
                self.canvas.create_text(ax, ay, text="✓", fill="#ffffff", font=("Segoe UI", 9, "bold"), tags="dynamic")
                self.canvas.create_text(ax, ay - nr - 5, text=f"N{a.id} Verified", fill="#34d399", font=("Segoe UI", 8, "bold"), tags="dynamic")
            elif a.discovered or self.wizard_step < 5:
                p_color = a.color
                p_outline = a.type_info["outline"]

                # Node circular beacon
                self.canvas.create_oval(ax - (nr + 4), ay - (nr + 4), ax + (nr + 4), ay + (nr + 4), outline=p_outline, width=2, dash=(2, 2), tags="dynamic")
                self.canvas.create_oval(ax - nr, ay - nr, ax + nr, ay + nr, fill=p_color, outline="#ffffff", width=2, tags="dynamic")

                icon_letter = "Y" if a.type_key == "yellowish" else ("B" if a.type_key == "growth" else "D")
                self.canvas.create_text(ax, ay, text=f"{icon_letter}{a.id}", fill="#ffffff", font=("Segoe UI", 8, "bold"), tags="dynamic")

                badge_txt = f"{a.type_info['badge']} ({a.size_info['icon']})"
                bw = max(42, int(46 * math.sqrt(self.zoom_level)))
                self.canvas.create_rectangle(ax - bw, ay + nr + 2, ax + bw, ay + nr + 16, fill="#090d16", outline=p_color, tags="dynamic")
                self.canvas.create_text(ax, ay + nr + 9, text=badge_txt, fill=p_outline, font=("Segoe UI", 7, "bold"), tags="dynamic")
            else:
                self.canvas.create_oval(ax - 5, ay - 5, ax + 5, ay + 5, fill="", outline="#64748b", dash=(2, 2), tags="dynamic")

        # 8. Drone Trails
        if len(self.master_drone.trail) > 1 and self.wizard_step == 5:
            m_coords = [self.metres_to_canvas(x, y) for (x, y) in self.master_drone.trail]
            for i in range(len(m_coords) - 1):
                self.canvas.create_line(
                    m_coords[i][0], m_coords[i][1], m_coords[i + 1][0], m_coords[i + 1][1],
                    fill="#38bdf8", width=2, tags="dynamic"
                )

        if self.wizard_step == 5:
            for idx, d in enumerate(self.swarm_drones):
                d_color = FLEET_COLORS[(idx + 1) % len(FLEET_COLORS)]
                if len(d.trail) > 1:
                    d_coords = [self.metres_to_canvas(x, y) for (x, y) in d.trail]
                    for i in range(len(d_coords) - 1):
                        self.canvas.create_line(
                            d_coords[i][0], d_coords[i][1], d_coords[i + 1][0], d_coords[i + 1][1],
                            fill=d_color, width=2, tags="dynamic"
                        )

                # Swarm breadcrumb trails rendered in fleet colors

        # 9. Mesh Comms Links
        if self.wizard_step == 5:
            mx, my = self.metres_to_canvas(self.master_drone.x, self.master_drone.y)

            if self.master_drone.status in ("SCANNING", "RETURNING_BASE"):
                self.canvas.create_line(bx, by, mx, my, fill="#0ea5e9", dash=(6, 4), width=1, tags="dynamic")
                px = bx + (mx - bx) * self.comms_pulse
                py = by + (my - by) * self.comms_pulse
                self.canvas.create_oval(px - 3, py - 3, px + 3, py + 3, fill="#38bdf8", outline="#ffffff", tags="dynamic")

            for d in self.swarm_drones:
                if d.status in ("TRAVELLING", "INSPECTING", "RETURNING", "LOW_BATTERY"):
                    dx, dy = self.metres_to_canvas(d.x, d.y)
                    self.canvas.create_line(bx, by, dx, dy, fill="#ec4899", dash=(4, 6), width=1, tags="dynamic")
                    spx = bx + (dx - bx) * self.comms_pulse
                    spy = by + (dy - by) * self.comms_pulse
                    self.canvas.create_oval(spx - 3, spy - 3, spx + 3, spy + 3, fill="#f472b6", outline="#ffffff", tags="dynamic")

        # 10. Master Drone Render with Height-Scaled Optical Footprint and Radar Cone
        self.render_drone_footprint_coverage()

        mx, my = self.metres_to_canvas(self.master_drone.x, self.master_drone.y)
        self.canvas.create_oval(mx - 18, my + 8, mx + 18, my + 20, fill="#020617", outline="", tags="dynamic")

        if self.master_drone.status == "SCANNING" and self.wizard_step == 5:
            fw_m, fh_m = self.calculate_camera_footprint(self.scout_altitude_m)
            fw_px = (fw_m / self.field_w_m) * (self.canvas_w - 64) * self.zoom_level

            # Sweeping Radar Cone ahead of drone
            cone_span_deg = 35.0
            rad_l = (fw_px / 2.0) * 1.15
            c1_rad = math.radians(self.master_drone.heading_deg - cone_span_deg)
            c2_rad = math.radians(self.master_drone.heading_deg + cone_span_deg)

            p1x = mx + rad_l * math.sin(c1_rad)
            p1y = my - rad_l * math.cos(c1_rad)
            p2x = mx + rad_l * math.sin(c2_rad)
            p2y = my - rad_l * math.cos(c2_rad)

            self.canvas.create_line(mx, my, p1x, p1y, fill="#0ea5e9", width=1, dash=(3, 3), tags="dynamic")
            self.canvas.create_line(mx, my, p2x, p2y, fill="#0ea5e9", width=1, dash=(3, 3), tags="dynamic")

            sweep_rad = math.radians(self.master_drone.heading_deg + self.radar_sweep_cone)
            sw_x = mx + rad_l * math.sin(sweep_rad)
            sw_y = my - rad_l * math.cos(sweep_rad)
            self.canvas.create_line(mx, my, sw_x, sw_y, fill="#38bdf8", width=2, tags="dynamic")

        if self.icon_master:
            self.canvas.create_image(mx, my, image=self.icon_master, tags="dynamic")
        else:
            self.canvas.create_oval(mx - 14, my - 14, mx + 14, my + 14, fill="#0284c7", outline="#ffffff", width=2, tags="dynamic")

        self.canvas.create_oval(mx - 24, my - 24, mx + 24, my + 24, outline="#38bdf8", width=2, tags="dynamic")

        # Heading pointer
        hx = mx + 26 * math.sin(math.radians(self.master_drone.heading_deg))
        hy = my - 26 * math.cos(math.radians(self.master_drone.heading_deg))
        self.canvas.create_line(mx, my, hx, hy, fill="#38bdf8", width=2, arrow=tk.LAST, tags="dynamic")

        self.canvas.create_rectangle(mx - 68, my - 34, mx + 68, my - 18, fill="#0369a1", outline="#ffffff", tags="dynamic")
        self.canvas.create_text(mx, my - 26, text="MASTER SCOUT D0", fill="#ffffff", font=("Segoe UI", 8, "bold"), tags="dynamic")

        # 11. Swarm Drones Render with Multispectral Scanning Reticles & Collision Rings
        if self.wizard_step == 5:
            for idx, d in enumerate(self.swarm_drones):
                dx, dy = self.metres_to_canvas(d.x, d.y)
                d_color = FLEET_COLORS[(idx + 1) % len(FLEET_COLORS)]

                self.canvas.create_oval(dx - 12, dy + 5, dx + 12, dy + 13, fill="#020617", outline="", tags="dynamic")

                if d.status == "FAILED":
                    self.canvas.create_line(dx - 14, dy - 14, dx + 14, dy + 14, fill="#dc2626", width=4, tags="dynamic")
                    self.canvas.create_line(dx - 14, dy + 14, dx + 14, dy - 14, fill="#dc2626", width=4, tags="dynamic")
                    self.canvas.create_rectangle(dx - 55, dy + 14, dx + 55, dy + 28, fill="#be123c", outline="#ffffff", tags="dynamic")
                    self.canvas.create_text(dx, dy + 21, text=f"D{d.id} HARD_FAILURE", fill="#ffffff", font=("Segoe UI", 7, "bold"), tags="dynamic")
                else:
                    # Collision avoidance warning ring if holding position
                    if d.holding_position:
                        self.canvas.create_oval(dx - 28, dy - 28, dx + 28, dy + 28, outline="#fbbf24", width=2, dash=(2, 2), tags="dynamic")
                        self.canvas.create_text(dx, dy + 32, text="HOLDING (SEPARATION)", fill="#fbbf24", font=("Segoe UI", 7, "bold"), tags="dynamic")

                    # Shortest-Path Dynamic Vector Visualization with High-Contrast Path Highlighting
                    if d.status == "TRAVELLING" and d.current_task_id is not None:
                        target_node = next((a for a in self.anomalies if a.id == d.current_task_id), None)
                        if target_node:
                            tx, ty = self.metres_to_canvas(target_node.x, target_node.y)
                            # Wide neon glow corridor underneath
                            self.canvas.create_line(dx, dy, tx, ty, fill=d_color, width=6, stipple="gray50", tags="dynamic")
                            # Crisp animated dashed trajectory vector
                            self.canvas.create_line(dx, dy, tx, ty, fill=d_color, width=2.5, dash=(6, 3), arrow=tk.LAST, tags="dynamic")

                            mid_x = (dx + tx) / 2.0
                            mid_y = (dy + ty) / 2.0
                            dist_m = math.hypot(d.x - target_node.x, d.y - target_node.y)
                            est_wh = dist_m * 0.20
                            # High-visibility trajectory badge
                            self.canvas.create_rectangle(mid_x - 46, mid_y - 9, mid_x + 46, mid_y + 9, fill="#090d16", outline=d_color, width=1.5, tags="dynamic")
                            self.canvas.create_text(mid_x, mid_y, text=f"⚡ D{d.id}➔N{target_node.id} | {dist_m:.1f}m ({est_wh:.0f}Wh)", fill="#ffffff", font=("Segoe UI", 6, "bold"), tags="dynamic")
                    elif d.status in ("RETURNING", "LOW_BATTERY"):
                        bx_coord, by_coord = self.get_drone_base_coords(d)
                        cbx, cby = self.metres_to_canvas(bx_coord, by_coord)
                        self.canvas.create_line(dx, dy, cbx, cby, fill="#f59e0b", width=2, dash=(4, 3), arrow=tk.LAST, tags="dynamic")
                        mid_x = (dx + cbx) / 2.0
                        mid_y = (dy + cby) / 2.0
                        self.canvas.create_rectangle(mid_x - 32, mid_y - 8, mid_x + 32, mid_y + 8, fill="#090d16", outline="#f59e0b", width=1, tags="dynamic")
                        self.canvas.create_text(mid_x, mid_y, text=f"D{d.id} ➔ RTH", fill="#fbbf24", font=("Segoe UI", 6, "bold"), tags="dynamic")

                    if d.status == "INSPECTING":
                        # Rotating Multispectral Laser Reticle
                        rr = max(24, int(32 * math.sqrt(self.zoom_level)))
                        self.canvas.create_oval(dx - rr, dy - rr, dx + rr, dy + rr, outline=d_color, width=2, tags="dynamic")
                        rx = dx + rr * math.cos(math.radians(self.radar_scan_angle))
                        ry = dy + rr * math.sin(math.radians(self.radar_scan_angle))
                        self.canvas.create_line(dx, dy, rx, ry, fill="#ffffff", width=2, tags="dynamic")

                        self.canvas.create_line(dx - 18, dy, dx + 18, dy, fill=d_color, width=1, dash=(2, 2), tags="dynamic")
                        self.canvas.create_line(dx, dy - 18, dx, dy + 18, fill=d_color, width=1, dash=(2, 2), tags="dynamic")

                        # Live rescan progress bar below drone
                        task = next((a for a in self.anomalies if a.id == d.current_task_id), None)
                        if task:
                            pct = int(min(100.0, task.rescan_progress * 100))
                            bar_w = 64
                            bar_h = 7
                            bx1 = dx - bar_w / 2
                            by1 = dy + rr + 5
                            self.canvas.create_rectangle(bx1, by1, bx1 + bar_w, by1 + bar_h, fill="#090d16", outline=d_color, tags="dynamic")
                            fill_w = int((bar_w - 2) * min(1.0, task.rescan_progress))
                            if fill_w > 0:
                                self.canvas.create_rectangle(bx1 + 1, by1 + 1, bx1 + 1 + fill_w, by1 + bar_h - 1, fill=d_color, outline="", tags="dynamic")
                            self.canvas.create_text(dx, by1 + bar_h + 8, text=f"RESCANNING {pct}%", fill="#ffffff", font=("Consolas", 6, "bold"), tags="dynamic")

                    if self.icon_swarm:
                        self.canvas.create_image(dx, dy, image=self.icon_swarm, tags="dynamic")
                    else:
                        self.canvas.create_oval(dx - 10, dy - 10, dx + 10, dy + 10, fill=d_color, outline="#ffffff", width=2, tags="dynamic")

                    self.canvas.create_oval(dx - 18, dy - 18, dx + 18, dy + 18, outline=d_color, width=2, tags="dynamic")

                    pill_bg = "#ca8a04" if d.status == "INSPECTING" else ("#b45309" if d.status == "LOW_BATTERY" else ("#090d16" if d.status == "STANDBY" else "#0f766e"))
                    self.canvas.create_rectangle(dx - 48, dy - 28, dx + 48, dy - 14, fill=pill_bg, outline="#ffffff", tags="dynamic")
                    self.canvas.create_text(dx, dy - 21, text=f"Swarm D{d.id} ({d.status})", fill="#ffffff", font=("Segoe UI", 7, "bold"), tags="dynamic")

        # 12. Cockpit HUD Overlay Card (Top-Left) & Mission Stage Announcement Banner (Top-Center)
        self.canvas.create_rectangle(14, 14, 490, 62, fill="#090d16", outline="#38bdf8", width=1.5, tags="dynamic")
        m_lat, m_lon = metres_to_gps(self.master_drone.x, self.master_drone.y)
        profile = CROP_PROFILES.get(self.selected_crop_name, {})
        fw_disp, fh_disp = self.calculate_camera_footprint(self.scout_altitude_m)
        stage_desc = (
            "STAGE 1: Master Scout Airborne (Grid Survey)" if self.mission_phase == 1
            else ("STAGE 2: Multi-Drone Swarm Active (Collaborative Inspection)" if self.mission_phase == 2
            else ("STAGE 3: Mission Complete (All Targets Verified)" if self.mission_phase == 3 else "Standby / Setup"))
        )
        active_swarms = sum(1 for d in self.swarm_drones if d.status in ("TRAVELLING", "INSPECTING", "RETURNING"))
        hud_txt = (
            f"Crop: {self.selected_crop_name.split()[0]} | Alt: {self.scout_altitude_m:.1f}m (Footprint: {fw_disp:.1f}m × {fh_disp:.1f}m)\n"
            f"Master D0: {self.master_drone.status} ({m_lat:.5f}°N, {m_lon:.5f}°E) | Fleet: {active_swarms} Airborne\n"
            f"Phase: {stage_desc}"
        )
        self.canvas.create_text(22, 38, text=hud_txt, fill="#38bdf8", font=("Consolas", 8), anchor=tk.W, tags="dynamic")

        # Top-Center Mission Stage Announcement Banner
        if self.wizard_step == 5:
            center_x = self.canvas_w / 2.0
            if self.mission_phase == 1:
                self.canvas.create_rectangle(center_x - 170, 14, center_x + 170, 44, fill="#090d16", outline="#0284c7", width=1.5, tags="dynamic")
                self.canvas.create_text(center_x, 29, text="📡 STAGE 1: MASTER SCOUT AIRBORNE", fill="#38bdf8", font=("Segoe UI", 8, "bold"), tags="dynamic")
            elif self.mission_phase == 2:
                self.canvas.create_rectangle(center_x - 190, 14, center_x + 190, 44, fill="#090d16", outline="#10b981", width=2, tags="dynamic")
                self.canvas.create_text(center_x, 29, text=f"🚀 STAGE 2: SWARM FLEET DEPLOYED ({active_swarms} ACTIVE)", fill="#34d399", font=("Segoe UI", 8, "bold"), tags="dynamic")
            elif self.mission_phase == 3:
                self.canvas.create_rectangle(center_x - 180, 14, center_x + 180, 44, fill="#090d16", outline="#22c55e", width=2, tags="dynamic")
                self.canvas.create_text(center_x, 29, text="✅ STAGE 3: MISSION ACCOMPLISHED", fill="#4ade80", font=("Segoe UI", 8, "bold"), tags="dynamic")

        # 13. Dynamic Map Scale Bar (Bottom-Left)
        self.render_map_scale()

        # 14. Aviation Compass Rose (Bottom-Right)
        self.render_compass_rose()


def main():
    root = tk.Tk()
    app = AgriVyaanSimulationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
