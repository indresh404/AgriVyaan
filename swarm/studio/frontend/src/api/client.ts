// REST API Client for AgriVyaan Mission Studio Backend

export interface ProjectSummary {
  id: string;
  name: string;
  base_lat: number;
  base_lon: number;
  created_at: string;
  updated_at: string;
}

export interface FieldData {
  id?: number;
  project_id?: string;
  polygon_geojson: any;
  area_m2: number;
  area_ha: number;
  area_acres: number;
  perimeter_m: number;
  bounds_json: {
    north: number;
    south: number;
    west: number;
    east: number;
  };
}

export interface CropData {
  crop_type: string;
  row_spacing_m: number;
  row_angle_deg: number;
}

export interface CameraData {
  preset_name: string;
  sensor_w_mm: number;
  sensor_h_mm: number;
  focal_length_mm: number;
  image_w_px: number;
  image_h_px: number;
  altitude_survey_m: number;
  altitude_detail_m: number;
  speed_survey_m_s: number;
  speed_detail_m_s: number;
  edge_margin: number;
  grid_angle_deg: number;
}

export interface DroneItem {
  drone_id: number;
  is_backup: boolean;
  capacity_Wh: number;
  power_hover_W: number;
  power_cruise_W: number;
  power_climb_W: number;
  reserve_pct: number;
  initial_charge_pct: number;
  drain_multiplier: number;
}

export interface HotspotItem {
  node_id: string;
  lat: number;
  lon: number;
  type: string;
  severity: number;
  note?: string;
  image_ref?: string;
}

export interface WaypointItem {
  index: number;
  cell_id?: string;
  lat: number;
  lon: number;
  x_m: number;
  y_m: number;
  altitude_m: number;
  action: string;
}

export interface PathEvaluation {
  drone_id: number;
  num_waypoints: number;
  num_captures: number;
  path_length_m: number;
  total_time_s: number;
  total_time_min: number;
  energy_used_Wh: number;
  remaining_Wh: number;
  remaining_battery_pct: number;
  is_battery_sufficient: boolean;
  earliest_rth_waypoint_index: number;
  rth_reason: string;
}

export interface PlanPreviewResponse {
  footprint: {
    altitude_m: number;
    footprint_w_m: number;
    footprint_h_m: number;
    gsd_mm_per_px: number;
    coverage_area_per_shot_m2: number;
  };
  grid: {
    altitude_m: number;
    cell_side_m: number;
    margin: number;
    grid_angle_deg: number;
    total_cells: number;
    kept_cells: number;
    field_area_m2: number;
    cells_covered_area_m2: number;
    coverage_fraction: number;
    coverage_pct: number;
    cells: Array<{
      cell_id: string;
      row: number;
      col: number;
      center_lat: number;
      center_lon: number;
      center_x_m: number;
      center_y_m: number;
      polygon_latlon: [number, number][];
      fraction_inside: number;
    }>;
  };
  active_drones_count: number;
  backup_drones_count: number;
  drone_evaluations: PathEvaluation[];
  drone_paths: Record<number, WaypointItem[]>;
}

export interface PlanValidationResponse {
  is_valid: boolean;
  checks: Array<{
    name: string;
    passed: boolean;
    details: string;
  }>;
  uncovered_cell_ids: string[];
  messages: string[];
}

const API_BASE = '/api';

export async function fetchHealth() {
  const r = await fetch(`${API_BASE}/health`);
  return r.json();
}

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const r = await fetch(`${API_BASE}/projects`);
  return r.json();
}

export async function createProject(name: string, base_lat = 18.52043, base_lon = 73.85671): Promise<ProjectSummary> {
  const r = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, base_lat, base_lon }),
  });
  return r.json();
}

export async function fetchProjectDetails(projectId: string) {
  const r = await fetch(`${API_BASE}/projects/${projectId}`);
  return r.json();
}

export async function updateField(projectId: string, coordinates: [number, number][], base_lat?: number, base_lon?: number) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/field`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ coordinates, base_lat, base_lon }),
  });
  return r.json();
}

export async function updateCrop(projectId: string, crop: CropData) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/crop`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(crop),
  });
  return r.json();
}

export async function updateCamera(projectId: string, camera: CameraData) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/camera`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(camera),
  });
  return r.json();
}

export async function updateDrones(projectId: string, drones: DroneItem[]) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/drones`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(drones),
  });
  return r.json();
}

export async function updateHotspots(projectId: string, hotspots: HotspotItem[]) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/hotspots`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(hotspots),
  });
  return r.json();
}

export async function previewPlan(projectId: string): Promise<PlanPreviewResponse> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/plan/preview`, {
    method: 'POST',
  });
  return r.json();
}

export async function validatePlan(projectId: string): Promise<PlanValidationResponse> {
  const r = await fetch(`${API_BASE}/projects/${projectId}/plan/validate`, {
    method: 'POST',
  });
  return r.json();
}

export async function prepareImagery(projectId: string) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/imagery/prepare`, {
    method: 'POST',
  });
  return r.json();
}

export async function runSimulation(projectId: string, seed = 42) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed }),
  });
  return r.json();
}

export async function fetchRecording(runId: string) {
  const r = await fetch(`${API_BASE}/runs/${runId}/recording`);
  return r.json();
}

export async function fetchPotatoProfile() {
  const r = await fetch(`${API_BASE}/crops/potato`);
  return r.json();
}

export async function exportProjectJson(projectId: string) {
  const r = await fetch(`${API_BASE}/projects/${projectId}/export`);
  return r.json();
}

export async function importProjectJson(data: any) {
  const r = await fetch(`${API_BASE}/projects/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return r.json();
}

export async function importGeoJson(content: string) {
  const r = await fetch(`${API_BASE}/geo/import-geojson`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return r.json();
}

export async function importKml(content: string) {
  const r = await fetch(`${API_BASE}/geo/import-kml`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return r.json();
}
