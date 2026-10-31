import { create } from 'zustand';

export interface SimCapture {
  id: string;
  t: number;
  drone_id: number;
  stage: number;
  cell_id?: string;
  lat: number;
  lon: number;
  alt: number;
  heading: number;
  footprint_polygon: [number, number][];
  gsd_mm_per_px: number;
  temp_c: number;
  rh_pct: number;
  battery_pct: number;
  image_url: string;
  thumb_url: string;
  label: string;
  hotspot_type?: string;
  hotspot_severity: number;
}

export interface SimEvent {
  t: number;
  type: string;
  drone_id?: number;
  target_id?: string;
  detail: string;
}

export interface DecisionRecord {
  t: number;
  drone_id: number;
  rule: string;
  candidates: Array<{
    cluster_id: string;
    distance_m: number;
    energy_Wh: number;
    priority: number;
    score: number;
    feasible: boolean;
  }>;
  chosen_cluster_id?: string;
  reason: string;
}

export interface SimRecording {
  schema_version: number;
  config_snapshot: any;
  seed: number;
  frames: Array<{
    t: number;
    drones: Array<{
      id: number;
      lat: number;
      lon: number;
      alt: number;
      heading: number;
      battery_pct: number;
      state: string;
      target_id?: string;
    }>;
  }>;
  events: SimEvent[];
  decisions: DecisionRecord[];
  captures: SimCapture[];
  summary: {
    total_time_s: number;
    total_distance_m: number;
    total_captures: number;
    coverage_pct: number;
    hotspots_total: number;
    hotspots_revealed: number;
    handovers_count: number;
    energy_used_per_drone_Wh: Record<number, number>;
    drones_used: number[];
  };
}

export interface SimLayers {
  grid: boolean;
  footprints: boolean;
  paths: boolean;
  trails: boolean;
  coverage: boolean;
  hotspots: boolean;
  cropRows: boolean;
}

export interface SimState {
  recording: SimRecording | null;
  currentTime: number;
  isPlaying: boolean;
  playbackSpeed: number;
  selectedCapture: SimCapture | null;
  isInspectorOpen: boolean;
  followDroneId: number | null;
  cinematicMode: boolean;
  layers: SimLayers;

  // Actions
  setRecording: (rec: SimRecording) => void;
  setCurrentTime: (t: number) => void;
  setIsPlaying: (playing: boolean) => void;
  togglePlay: () => void;
  setPlaybackSpeed: (speed: number) => void;
  setSelectedCapture: (cap: SimCapture | null) => void;
  setIsInspectorOpen: (open: boolean) => void;
  setFollowDroneId: (id: number | null) => void;
  toggleCinematicMode: () => void;
  toggleLayer: (layerKey: keyof SimLayers) => void;
  jumpToNextEvent: () => void;
  jumpToPrevEvent: () => void;
}

export const useSimStore = create<SimState>((set, get) => ({
  recording: null,
  currentTime: 0.0,
  isPlaying: false,
  playbackSpeed: 1.0,
  selectedCapture: null,
  isInspectorOpen: false,
  followDroneId: null,
  cinematicMode: false,
  layers: {
    grid: true,
    footprints: true,
    paths: true,
    trails: true,
    coverage: true,
    hotspots: true,
    cropRows: true,
  },

  setRecording: (rec) =>
    set({
      recording: rec,
      currentTime: 0.0,
      isPlaying: false,
      selectedCapture: rec.captures.length > 0 ? rec.captures[0] : null,
    }),

  setCurrentTime: (t) => {
    const rec = get().recording;
    const maxT = rec ? rec.summary.total_time_s : 0;
    const clamped = Math.max(0, Math.min(maxT, t));
    set({ currentTime: clamped });

    // Check if capture occurred near this time for inspector auto-update
    if (rec && rec.captures.length > 0) {
      const activeCaps = rec.captures.filter((c) => c.t <= clamped);
      if (activeCaps.length > 0) {
        const latest = activeCaps[activeCaps.length - 1];
        if (!get().selectedCapture || get().selectedCapture!.id !== latest.id) {
          set({ selectedCapture: latest });
        }
      }
    }
  },

  setIsPlaying: (isPlaying) => set({ isPlaying }),
  togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),
  setPlaybackSpeed: (playbackSpeed) => set({ playbackSpeed }),
  setSelectedCapture: (selectedCapture) =>
    set({ selectedCapture, isInspectorOpen: selectedCapture !== null }),
  setIsInspectorOpen: (isInspectorOpen) => set({ isInspectorOpen }),
  setFollowDroneId: (followDroneId) => set({ followDroneId }),
  toggleCinematicMode: () => set((state) => ({ cinematicMode: !state.cinematicMode })),
  toggleLayer: (layerKey) =>
    set((state) => ({
      layers: { ...state.layers, [layerKey]: !state.layers[layerKey] },
    })),

  jumpToNextEvent: () => {
    const { recording, currentTime } = get();
    if (!recording) return;
    const nextEv = recording.events.find((ev) => ev.t > currentTime + 0.1);
    if (nextEv) {
      get().setCurrentTime(nextEv.t);
    }
  },

  jumpToPrevEvent: () => {
    const { recording, currentTime } = get();
    if (!recording) return;
    const prevEvs = recording.events.filter((ev) => ev.t < currentTime - 0.1);
    if (prevEvs.length > 0) {
      const last = prevEvs[prevEvs.length - 1];
      get().setCurrentTime(last.t);
    } else {
      get().setCurrentTime(0.0);
    }
  },
}));
