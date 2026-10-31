import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { formatArea, formatDistance } from '../lib/format';
import { importGeoJson, importKml } from '../api/client';
import { PenTool, Upload, RefreshCw, FileText } from 'lucide-react';

export const Step2Field: React.FC = () => {
  const { field, project, updateFieldCoords } = useProjectStore();
  const [importText, setImportText] = useState('');
  const [showImportBox, setShowImportBox] = useState(false);
  const [importMsg, setImportMsg] = useState('');

  const areaInfo = formatArea(field?.area_m2 || 0);

  const handleResetSquare = () => {
    if (!project) return;
    const lat = project.base_lat;
    const lon = project.base_lon;
    const dLat = 0.0009;
    const dLon = 0.0009;
    const coords: [number, number][] = [
      [lat, lon],
      [lat + dLat, lon],
      [lat + dLat, lon + dLon],
      [lat, lon + dLon],
    ];
    updateFieldCoords(coords, lat, lon);
  };

  const handleRunImport = async (type: 'geojson' | 'kml') => {
    try {
      setImportMsg('Parsing...');
      let res;
      if (type === 'geojson') {
        res = await importGeoJson(importText);
      } else {
        res = await importKml(importText);
      }
      if (res.coordinates && res.coordinates.length >= 3) {
        await updateFieldCoords(res.coordinates);
        setImportMsg(`✅ Successfully imported ${res.coordinates.length} vertices.`);
        setShowImportBox(false);
      } else {
        setImportMsg('❌ Failed: Less than 3 valid coordinates found.');
      }
    } catch (e: any) {
      setImportMsg(`❌ Error: ${e.message}`);
    }
  };

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <PenTool className="w-5 h-5 text-emerald-400" />
          Step 2: Field Boundary & Real Geometry
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Draw or edit the farm boundary polygon. All geometric formulas are calculated in local metric UTM projection.
        </p>
      </div>

      {/* Live Measurement Cards */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-900 border border-slate-700/80 rounded p-2.5">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">Survey Area</span>
          <div className="text-base font-bold text-emerald-400 mt-0.5">{areaInfo.m2}</div>
          <div className="text-[11px] text-slate-300">
            {areaInfo.ha} / {areaInfo.acres}
          </div>
        </div>
        <div className="bg-slate-900 border border-slate-700/80 rounded p-2.5">
          <span className="text-[11px] text-slate-400 uppercase font-semibold">Perimeter</span>
          <div className="text-base font-bold text-sky-400 mt-0.5">
            {formatDistance(field?.perimeter_m || 0)}
          </div>
          <div className="text-[11px] text-slate-300">
            {field?.bounds_json ? 'Georeferenced WGS84' : 'Awaiting Polygon'}
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleResetSquare}
          className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium py-1.5 px-3 rounded flex items-center justify-center gap-1.5 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Reset to 1 Ha Square
        </button>
        <button
          onClick={() => setShowImportBox(!showImportBox)}
          className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium py-1.5 px-3 rounded flex items-center justify-center gap-1.5 transition"
        >
          <Upload className="w-3.5 h-3.5" />
          Import GeoJSON/KML
        </button>
      </div>

      {showImportBox && (
        <div className="bg-slate-900/90 border border-slate-700 rounded p-3 space-y-2 text-xs">
          <label className="font-semibold text-slate-200">Paste GeoJSON or KML Polygon Content:</label>
          <textarea
            rows={4}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder='{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[...]]}}'
            className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-300 font-mono text-[11px]"
          />
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-amber-400">{importMsg}</span>
            <div className="flex gap-2">
              <button
                onClick={() => handleRunImport('geojson')}
                className="bg-emerald-700 hover:bg-emerald-600 text-white px-2.5 py-1 rounded text-xs"
              >
                Import GeoJSON
              </button>
              <button
                onClick={() => handleRunImport('kml')}
                className="bg-sky-700 hover:bg-sky-600 text-white px-2.5 py-1 rounded text-xs"
              >
                Import KML
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-slate-900/60 border border-slate-800 rounded p-2.5 text-xs text-slate-400">
        💡 <strong className="text-slate-300">Map Drawing Tip:</strong> Click vertices on the satellite map to reposition them or click edges to add new boundary vertices.
      </div>
    </div>
  );
};
