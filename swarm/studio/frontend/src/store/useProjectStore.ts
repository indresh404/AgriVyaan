import { create } from 'zustand';
import * as api from '../api/client';

export interface ProjectState {
  screen: 'wizard' | 'sim';
  wizardStep: number;
  project: api.ProjectSummary | null;
  field: api.FieldData | null;
  crop: api.CropData;
  camera: api.CameraData;
  drones: api.DroneItem[];
  hotspots: api.HotspotItem[];
  preview: api.PlanPreviewResponse | null;
  validation: api.PlanValidationResponse | null;
  cropRows: [number, number][][];
  isLoading: boolean;
  error: string | null;

  // Actions
  setScreen: (screen: 'wizard' | 'sim') => void;
  setWizardStep: (step: number) => void;
  loadProject: (projectId: string) => Promise<void>;
  createDefaultProject: () => Promise<void>;
  updateFieldCoords: (coords: [number, number][], baseLat?: number, baseLon?: number) => Promise<void>;
  updateCropSettings: (crop: Partial<api.CropData>) => Promise<void>;
  updateCameraSettings: (camera: Partial<api.CameraData>) => Promise<void>;
  updateDroneList: (drones: api.DroneItem[]) => Promise<void>;
  addHotspot: (hotspot: api.HotspotItem) => Promise<void>;
  removeHotspot: (nodeId: string) => Promise<void>;
  fetchPreview: () => Promise<void>;
  validateCurrentPlan: () => Promise<boolean>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  screen: 'wizard',
  wizardStep: 1,
  project: null,
  field: null,
  crop: {
    crop_type: 'potato',
    row_spacing_m: 0.75,
    row_angle_deg: 0.0,
  },
  camera: {
    preset_name: 'Pi Camera HQ (6mm Lens)',
    sensor_w_mm: 6.287,
    sensor_h_mm: 4.712,
    focal_length_mm: 6.0,
    image_w_px: 4056,
    image_h_px: 3040,
    altitude_survey_m: 20.0,
    altitude_detail_m: 8.0,
    speed_survey_m_s: 6.0,
    speed_detail_m_s: 3.5,
    edge_margin: 0.20,
    grid_angle_deg: 0.0,
  },
  drones: [
    {
      drone_id: 1,
      is_backup: false,
      capacity_Wh: 74.0,
      power_hover_W: 150.0,
      power_cruise_W: 160.0,
      power_climb_W: 220.0,
      reserve_pct: 25.0,
      initial_charge_pct: 100.0,
      drain_multiplier: 1.0,
    },
    {
      drone_id: 2,
      is_backup: false,
      capacity_Wh: 74.0,
      power_hover_W: 150.0,
      power_cruise_W: 160.0,
      power_climb_W: 220.0,
      reserve_pct: 25.0,
      initial_charge_pct: 100.0,
      drain_multiplier: 1.0,
    },
    {
      drone_id: 3,
      is_backup: true,
      capacity_Wh: 74.0,
      power_hover_W: 150.0,
      power_cruise_W: 160.0,
      power_climb_W: 220.0,
      reserve_pct: 25.0,
      initial_charge_pct: 100.0,
      drain_multiplier: 1.0,
    },
  ],
  hotspots: [],
  preview: null,
  validation: null,
  cropRows: [],
  isLoading: false,
  error: null,

  setScreen: (screen) => set({ screen }),
  setWizardStep: (step) => set({ wizardStep: Math.max(1, Math.min(8, step)) }),

  loadProject: async (projectId: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.fetchProjectDetails(projectId);
      set({
        project: data.project,
        field: data.field,
        crop: data.crop || get().crop,
        camera: data.camera || get().camera,
        drones: data.drones?.length ? data.drones : get().drones,
        hotspots: data.hotspots || [],
        isLoading: false,
      });
      if (data.field?.polygon_geojson) {
        get().fetchPreview();
      }
    } catch (e: any) {
      set({ error: e.message || 'Failed to load project', isLoading: false });
    }
  },

  createDefaultProject: async () => {
    set({ isLoading: true, error: null });
    try {
      const proj = await api.createProject('AgriVyaan Potato Demo Farm', 18.52043, 73.85671);
      set({ project: proj, isLoading: false });

      // Create default 100m x 100m square field
      const refLat = 18.52043;
      const refLon = 73.85671;
      const defaultCoords: [number, number][] = [
        [refLat, refLon],
        [refLat + 0.0009, refLon],
        [refLat + 0.0009, refLon + 0.0009],
        [refLat, refLon + 0.0009],
      ];
      await get().updateFieldCoords(defaultCoords, refLat, refLon);

      // Add 2 default ground-truth hotspots
      const defaultHotspots: api.HotspotItem[] = [
        {
          node_id: 'H-01',
          lat: refLat + 0.00035,
          lon: refLon + 0.00045,
          type: 'late_blight',
          severity: 0.92,
          note: 'Water-soaked lesion cluster in dense canopy',
        },
        {
          node_id: 'H-02',
          lat: refLat + 0.00065,
          lon: refLon + 0.0007,
          type: 'early_blight',
          severity: 0.76,
          note: 'Target-board necrotic rings on lower leaves',
        },
      ];
      await api.updateHotspots(proj.id, defaultHotspots);
      set({ hotspots: defaultHotspots });

      await get().fetchPreview();
    } catch (e: any) {
      set({ error: e.message || 'Failed to create default project', isLoading: false });
    }
  },

  updateFieldCoords: async (coords, baseLat, baseLon) => {
    const proj = get().project;
    if (!proj) return;
    try {
      const res = await api.updateField(proj.id, coords, baseLat, baseLon);
      set({ field: res.field, cropRows: res.crop_rows || [] });
      await get().fetchPreview();
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updateCropSettings: async (cropPatch) => {
    const proj = get().project;
    if (!proj) return;
    const updated = { ...get().crop, ...cropPatch };
    set({ crop: updated });
    try {
      await api.updateCrop(proj.id, updated);
      if (get().field?.polygon_geojson) {
        // Refresh crop rows
        const coords = get().field!.polygon_geojson.geometry.coordinates[0].map((pt: any) => [pt[1], pt[0]]);
        const res = await api.updateField(proj.id, coords);
        set({ cropRows: res.crop_rows || [] });
      }
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updateCameraSettings: async (camPatch) => {
    const proj = get().project;
    if (!proj) return;
    const updated = { ...get().camera, ...camPatch };
    set({ camera: updated });
    try {
      await api.updateCamera(proj.id, updated);
      await get().fetchPreview();
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updateDroneList: async (drones) => {
    const proj = get().project;
    if (!proj) return;
    set({ drones });
    try {
      await api.updateDrones(proj.id, drones);
      await get().fetchPreview();
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  addHotspot: async (hotspot) => {
    const proj = get().project;
    if (!proj) return;
    const list = [...get().hotspots.filter((h) => h.node_id !== hotspot.node_id), hotspot];
    set({ hotspots: list });
    try {
      await api.updateHotspots(proj.id, list);
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  removeHotspot: async (nodeId) => {
    const proj = get().project;
    if (!proj) return;
    const list = get().hotspots.filter((h) => h.node_id !== nodeId);
    set({ hotspots: list });
    try {
      await api.updateHotspots(proj.id, list);
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  fetchPreview: async () => {
    const proj = get().project;
    if (!proj) return;
    try {
      const prev = await api.previewPlan(proj.id);
      set({ preview: prev });
    } catch (e: any) {
      console.warn('Preview plan error:', e);
    }
  },

  validateCurrentPlan: async () => {
    const proj = get().project;
    if (!proj) return false;
    try {
      const val = await api.validatePlan(proj.id);
      set({ validation: val });
      return val.is_valid;
    } catch (e: any) {
      set({ error: e.message });
      return false;
    }
  },
}));
