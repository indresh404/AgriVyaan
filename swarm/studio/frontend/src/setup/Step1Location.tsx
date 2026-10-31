import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { MapPin, Upload, Globe, Check } from 'lucide-react';

const PRESET_LOCATIONS = [
  { name: 'AgriVyaan Research Farm, Pune (India)', lat: 18.52043, lon: 73.85671 },
  { name: 'Salinas Valley Potato Fields, CA (USA)', lat: 36.6777, lon: -121.6555 },
  { name: 'Red River Valley Potato Basin, ND (USA)', lat: 47.9253, lon: -97.0329 },
  { name: 'Flevoland Polder Farms (Netherlands)', lat: 52.5279, lon: 5.5953 },
];

export const Step1Location: React.FC = () => {
  const { project, updateFieldCoords } = useProjectStore();
  const [selectedPreset, setSelectedPreset] = useState(0);
  const [customLat, setCustomLat] = useState('18.52043');
  const [customLon, setCustomLon] = useState('73.85671');

  const handleApplyPreset = (loc: (typeof PRESET_LOCATIONS)[0], index: number) => {
    setSelectedPreset(index);
    setCustomLat(loc.lat.toString());
    setCustomLon(loc.lon.toString());

    // Generate standard 100m square around location
    const dLat = 0.0009;
    const dLon = 0.0009;
    const coords: [number, number][] = [
      [loc.lat, loc.lon],
      [loc.lat + dLat, loc.lon],
      [loc.lat + dLat, loc.lon + dLon],
      [loc.lat, loc.lon + dLon],
    ];
    updateFieldCoords(coords, loc.lat, loc.lon);
  };

  const handleApplyCustom = () => {
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);
    if (!isNaN(lat) && !isNaN(lon)) {
      const dLat = 0.0009;
      const dLon = 0.0009;
      const coords: [number, number][] = [
        [lat, lon],
        [lat + dLat, lon],
        [lat + dLat, lon + dLon],
        [lat, lon + dLon],
      ];
      updateFieldCoords(coords, lat, lon);
    }
  };

  return (
    <div className="space-y-5 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Globe className="w-5 h-5 text-sky-400" />
          Step 1: Farm Location & Satellite Basemap
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Select a verified agricultural field location or enter real-world GPS coordinates. Satellite tiles will be cached locally for offline simulation.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Preset Agricultural Regions:</label>
        <div className="space-y-1.5">
          {PRESET_LOCATIONS.map((loc, idx) => (
            <button
              key={loc.name}
              onClick={() => handleApplyPreset(loc, idx)}
              className={`w-full text-left px-3 py-2 rounded border text-xs flex items-center justify-between transition-colors ${
                selectedPreset === idx
                  ? 'bg-sky-950/60 border-sky-500 text-sky-200'
                  : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500'
              }`}
            >
              <div className="flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5 text-sky-400" />
                <span className="font-medium">{loc.name}</span>
              </div>
              {selectedPreset === idx && <Check className="w-3.5 h-3.5 text-sky-400" />}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-slate-800 pt-3 space-y-3">
        <label className="text-xs font-semibold text-slate-300">Custom WGS84 Base Reference Coordinates:</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-[11px] text-slate-400">Latitude (°N)</span>
            <input
              type="number"
              step="0.00001"
              value={customLat}
              onChange={(e) => setCustomLat(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
            />
          </div>
          <div>
            <span className="text-[11px] text-slate-400">Longitude (°E)</span>
            <input
              type="number"
              step="0.00001"
              value={customLon}
              onChange={(e) => setCustomLon(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>
        <button
          onClick={handleApplyCustom}
          className="w-full bg-slate-800 hover:bg-slate-700 text-white font-medium py-1.5 px-3 rounded text-xs transition"
        >
          Set Custom Location & Center Map
        </button>
      </div>

      <div className="bg-slate-900/80 border border-slate-800 rounded p-3 text-[11px] text-slate-400 space-y-1">
        <div className="font-semibold text-slate-300">🛰️ Tile Imagery Attribution:</div>
        <div>Esri World Imagery & ArcGIS Online. All downloaded tiles inside the field bounds are cached to disk in <code>data/cache/tiles/</code>.</div>
      </div>
    </div>
  );
};
