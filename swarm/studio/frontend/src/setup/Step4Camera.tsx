import React from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Camera, AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react';
import { formatGSD } from '../lib/format';

export const Step4Camera: React.FC = () => {
  const { camera, preview, updateCameraSettings } = useProjectStore();

  const handleAlignToLongestEdge = () => {
    // If preview or field computed angle exists, align grid
    updateCameraSettings({ grid_angle_deg: 0.0 });
  };

  const isAltWarning = camera.altitude_survey_m < 5.0 || camera.altitude_survey_m > 120.0;

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Camera className="w-5 h-5 text-indigo-400" />
          Step 4: Camera Optics & Survey Altitude
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Optical ground sampling distance (GSD), footprint width/height, and square grid generation.
        </p>
      </div>

      {/* Altitude warning if < 5m or > 120m */}
      {isAltWarning && (
        <div className="bg-red-950/80 border border-red-500 rounded p-2.5 text-xs text-red-200 flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <strong>Regulatory Altitude Warning:</strong> Planned altitude ({camera.altitude_survey_m}m) is outside standard safe limits (5m - 120m AGL). Check local civil aviation drone regulations.
          </div>
        </div>
      )}

      {/* Live Measurement Cards */}
      {preview && (
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-slate-900 border border-slate-700/80 rounded p-2.5">
            <span className="text-[11px] text-slate-400 font-semibold uppercase">Optical GSD</span>
            <div className="text-base font-bold text-indigo-400 mt-0.5">
              {formatGSD(preview.footprint.gsd_mm_per_px)}
            </div>
            <div className="text-[11px] text-slate-300">
              Footprint: {preview.footprint.footprint_w_m}m × {preview.footprint.footprint_h_m}m
            </div>
          </div>
          <div className="bg-slate-900 border border-slate-700/80 rounded p-2.5">
            <span className="text-[11px] text-slate-400 font-semibold uppercase">Coverage Grid</span>
            <div className="text-base font-bold text-emerald-400 mt-0.5">
              {preview.grid.coverage_pct}% Covered
            </div>
            <div className="text-[11px] text-slate-300">
              {preview.grid.kept_cells} Cells ({preview.grid.cell_side_m}m side)
            </div>
          </div>
        </div>
      )}

      {/* Inputs */}
      <div className="bg-slate-900 border border-slate-700 rounded p-3 space-y-3">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-[11px] text-slate-400 font-medium">Stage-1 Altitude (m)</span>
            <input
              type="number"
              step="1"
              min="5"
              max="120"
              value={camera.altitude_survey_m}
              onChange={(e) => updateCameraSettings({ altitude_survey_m: parseFloat(e.target.value) || 20.0 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-medium">Stage-2 Detail Altitude (m)</span>
            <input
              type="number"
              step="1"
              min="4"
              max="20"
              value={camera.altitude_detail_m}
              onChange={(e) => updateCameraSettings({ altitude_detail_m: parseFloat(e.target.value) || 8.0 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-medium">Edge Overlap Margin (0-0.5)</span>
            <input
              type="number"
              step="0.05"
              min="0.05"
              max="0.5"
              value={camera.edge_margin}
              onChange={(e) => updateCameraSettings({ edge_margin: parseFloat(e.target.value) || 0.2 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400 font-medium">Survey Speed (m/s)</span>
            <input
              type="number"
              step="0.5"
              min="2"
              max="15"
              value={camera.speed_survey_m_s}
              onChange={(e) => updateCameraSettings({ speed_survey_m_s: parseFloat(e.target.value) || 6.0 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
        </div>

        <div className="border-t border-slate-800 pt-2 flex items-center justify-between text-xs">
          <span className="text-slate-400">Grid Orientation: {camera.grid_angle_deg}°</span>
          <button
            onClick={handleAlignToLongestEdge}
            className="text-[11px] bg-slate-800 hover:bg-slate-700 text-sky-300 px-2 py-1 rounded"
          >
            Align to Grid Baseline
          </button>
        </div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded p-2.5 text-xs text-slate-400">
        🔬 <strong>Sensor Preset:</strong> Pi Camera HQ (6.287×4.712 mm sensor, 6mm focal lens, 4056×3040 px).
      </div>
    </div>
  );
};
