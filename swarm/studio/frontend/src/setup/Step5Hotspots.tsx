import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Target, Plus, Trash2, MapPin } from 'lucide-react';

const HOTSPOT_TYPES = [
  { id: 'late_blight', label: 'Late Blight (Phytophthora)', color: 'text-red-400' },
  { id: 'early_blight', label: 'Early Blight (Alternaria)', color: 'text-amber-400' },
  { id: 'aphid', label: 'Aphid / Insect Vector', color: 'text-purple-400' },
  { id: 'water_stress', label: 'Water Deficit / Wilting', color: 'text-blue-400' },
  { id: 'nutrient', label: 'Nutrient Stress (Chlorosis)', color: 'text-yellow-400' },
  { id: 'other', label: 'Other Canopy Anomaly', color: 'text-slate-400' },
];

export const Step5Hotspots: React.FC = () => {
  const { hotspots, project, addHotspot, removeHotspot } = useProjectStore();
  const [selectedType, setSelectedType] = useState('late_blight');
  const [severity, setSeverity] = useState(0.85);
  const [note, setNote] = useState('');

  const handleAddDefaultPin = () => {
    if (!project) return;
    const count = hotspots.length + 1;
    // Offset slightly from base
    const offset = 0.0003 + count * 0.00015;
    addHotspot({
      node_id: `H-${count.toString().padStart(2, '0')}`,
      lat: project.base_lat + offset,
      lon: project.base_lon + offset,
      type: selectedType,
      severity,
      note: note || `${selectedType.replace('_', ' ')} observation area`,
    });
    setNote('');
  };

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Target className="w-5 h-5 text-rose-400" />
          Step 5: Mark Ground-Truth Areas of Interest
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Define suspicious hotspots on the farm. Simulated UAVs will "discover" these zones during Stage 1 and micro-rescan them during Stage 2.
        </p>
      </div>

      {/* Add Hotspot Form */}
      <div className="bg-slate-900 border border-slate-700 rounded p-3 space-y-3">
        <div className="text-xs font-semibold text-slate-200">New Hotspot Marker:</div>
        <div>
          <span className="text-[11px] text-slate-400">Pathology / Stress Type</span>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-xs text-white mt-1"
          >
            {HOTSPOT_TYPES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-[11px] text-slate-400">Severity ({(severity * 100).toFixed(0)}%)</span>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={severity}
              onChange={(e) => setSeverity(parseFloat(e.target.value))}
              className="w-full mt-1.5"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400">Diagnostic Note</span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Lower leaves wilting"
              className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white mt-1"
            />
          </div>
        </div>

        <button
          onClick={handleAddDefaultPin}
          className="w-full bg-rose-700 hover:bg-rose-600 text-white font-medium py-1.5 px-3 rounded text-xs flex items-center justify-center gap-1.5 transition"
        >
          <Plus className="w-3.5 h-3.5" />
          Drop Hotspot Pin on Farm
        </button>
      </div>

      {/* Hotspots List */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-300">
          Marked Ground-Truth Hotspots ({hotspots.length}):
        </label>
        {hotspots.length === 0 ? (
          <div className="text-xs text-slate-500 italic p-3 text-center border border-slate-800 rounded bg-slate-950/40">
            No hotspots marked yet. Click above to drop a target zone.
          </div>
        ) : (
          <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
            {hotspots.map((h) => (
              <div
                key={h.node_id}
                className="bg-slate-900 border border-slate-800 rounded p-2 text-xs flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-rose-400" />
                    <span>{h.node_id}</span>
                    <span className="text-slate-400 font-normal capitalize">
                      ({h.type.replace('_', ' ')})
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Severity: {(h.severity * 100).toFixed(0)}% • {h.note || 'No notes'}
                  </div>
                </div>
                <button
                  onClick={() => removeHotspot(h.node_id)}
                  className="text-slate-500 hover:text-red-400 p-1"
                  title="Remove hotspot"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
