import React, { useEffect, useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { fetchPotatoProfile } from '../api/client';
import { Sprout, AlertCircle, Layers } from 'lucide-react';

export const Step3Crop: React.FC = () => {
  const { crop, updateCropSettings } = useProjectStore();
  const [profile, setProfile] = useState<any>(null);

  useEffect(() => {
    fetchPotatoProfile().then(setProfile).catch(console.error);
  }, []);

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Sprout className="w-5 h-5 text-amber-400" />
          Step 3: Crop Profile & Illustrative Row Pattern
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Select target agricultural crop to configure canopy feature sizes and row spacing.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Select Crop Variety:</label>
        <div className="grid grid-cols-2 gap-2">
          <button className="bg-amber-950/60 border-2 border-amber-500 rounded p-2.5 text-left text-xs">
            <div className="font-bold text-amber-200">🥔 Potato (Solanum tuberosum)</div>
            <div className="text-[11px] text-amber-400/80 mt-0.5">Fully Shipped & Supported</div>
          </button>
          <button disabled className="bg-slate-900/40 border border-slate-800 rounded p-2.5 text-left text-xs opacity-50 cursor-not-allowed">
            <div className="font-bold text-slate-400">🌽 Corn / Maize</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Profile not added yet</div>
          </button>
          <button disabled className="bg-slate-900/40 border border-slate-800 rounded p-2.5 text-left text-xs opacity-50 cursor-not-allowed">
            <div className="font-bold text-slate-400">🌾 Wheat / Barley</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Profile not added yet</div>
          </button>
          <button disabled className="bg-slate-900/40 border border-slate-800 rounded p-2.5 text-left text-xs opacity-50 cursor-not-allowed">
            <div className="font-bold text-slate-400">🍇 Grapevine Canopy</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Profile not added yet</div>
          </button>
        </div>
      </div>

      {/* Row Pattern Adjustment */}
      <div className="bg-slate-900 border border-slate-700 rounded p-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-sky-400" />
            Crop-Row Overlay Alignment:
          </span>
          <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
            Illustrative Overlay
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-[11px] text-slate-400">Row Spacing (m)</span>
            <input
              type="number"
              step="0.05"
              min="0.3"
              max="2.0"
              value={crop.row_spacing_m}
              onChange={(e) => updateCropSettings({ row_spacing_m: parseFloat(e.target.value) || 0.75 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400">Row Angle (deg)</span>
            <input
              type="number"
              step="5"
              min="0"
              max="180"
              value={crop.row_angle_deg}
              onChange={(e) => updateCropSettings({ row_angle_deg: parseFloat(e.target.value) || 0.0 })}
              className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
            />
          </div>
        </div>
        <p className="text-[11px] text-slate-500 italic">
          * Note: Illustrative overlay inside field polygon, not detected from satellite imagery.
        </p>
      </div>

      {profile && (
        <div className="bg-slate-900/80 border border-slate-800 rounded p-3 text-xs space-y-2">
          <div className="font-semibold text-amber-300">Target Pathologies & Feature Sizes:</div>
          <div className="space-y-1.5 text-[11px] text-slate-300">
            {profile.pathologies?.slice(0, 3).map((p: any) => (
              <div key={p.id} className="border-b border-slate-800 pb-1 flex justify-between">
                <span>{p.name}</span>
                <span className="text-amber-400 font-mono">{p.feature_size_mm} mm</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
