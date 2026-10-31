import React from 'react';
import { useSimStore } from '../store/useSimStore';
import { formatGSD, formatLatLon } from '../lib/format';
import { X, ChevronLeft, ChevronRight, Download, Thermometer, Droplets, Target, ShieldCheck } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export const CaptureInspector: React.FC = () => {
  const { recording, selectedCapture, isInspectorOpen, setSelectedCapture, setIsInspectorOpen, setCurrentTime } = useSimStore();

  if (!isInspectorOpen || !selectedCapture || !recording) return null;

  // Build telemetry history for chart
  const historyData = recording.captures
    .filter((c) => c.t <= selectedCapture.t)
    .slice(-15)
    .map((c) => ({
      t: c.t,
      temp: c.temp_c,
      rh: c.rh_pct,
    }));

  const currentIndex = recording.captures.findIndex((c) => c.id === selectedCapture.id);

  const handlePrev = () => {
    if (currentIndex > 0) {
      const prev = recording.captures[currentIndex - 1];
      setSelectedCapture(prev);
      setCurrentTime(prev.t);
    }
  };

  const handleNext = () => {
    if (currentIndex < recording.captures.length - 1) {
      const next = recording.captures[currentIndex + 1];
      setSelectedCapture(next);
      setCurrentTime(next.t);
    }
  };

  const handleExportJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(selectedCapture, null, 2));
    const a = document.createElement('a');
    a.href = dataStr;
    a.download = `${selectedCapture.id}.json`;
    a.click();
  };

  return (
    <div className="absolute top-16 right-4 z-20 w-[380px] bg-slate-950/95 border border-slate-700/80 rounded-xl shadow-2xl backdrop-blur-md overflow-hidden flex flex-col pointer-events-auto transition-all animate-in fade-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
          <span className="font-bold text-xs text-white">Capture Inspector: {selectedCapture.id}</span>
          <span className="text-[10px] font-mono bg-sky-950 text-sky-300 border border-sky-800 px-1.5 py-0.2 rounded">
            Stage {selectedCapture.stage}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={handleExportJson} className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white" title="Export JSON">
            <Download className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => setIsInspectorOpen(false)} className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="p-3.5 space-y-3 overflow-y-auto max-h-[calc(100vh-180px)] text-xs">
        {/* Enlarged Image */}
        <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-slate-900 aspect-[4/3] flex items-center justify-center">
          <img
            src={selectedCapture.image_url}
            alt={selectedCapture.label}
            className="w-full h-full object-cover"
            onError={(e) => {
              // Fallback to high-contrast simulated crop if image server cold
              (e.target as any).style.display = 'none';
            }}
          />
          {selectedCapture.hotspot_type && (
            <div className="absolute top-2 left-2 bg-red-950/90 border border-red-500 text-red-200 text-[10px] font-bold px-2 py-0.5 rounded shadow">
              🚨 {selectedCapture.label.toUpperCase()} ({(selectedCapture.hotspot_severity * 100).toFixed(0)}%)
            </div>
          )}
          <div className="absolute bottom-2 right-2 bg-slate-950/80 text-[10px] text-slate-400 px-1.5 py-0.5 rounded">
            {formatGSD(selectedCapture.gsd_mm_per_px)}
          </div>
        </div>

        {/* Optical & Flight Metrics */}
        <div className="grid grid-cols-2 gap-2 text-[11px] bg-slate-900/60 p-2.5 rounded border border-slate-800">
          <div>
            <span className="text-slate-400">Captured by:</span>{' '}
            <strong className="text-sky-300">Drone {selectedCapture.drone_id}</strong>
          </div>
          <div>
            <span className="text-slate-400">Time:</span>{' '}
            <strong className="text-slate-200">{selectedCapture.t.toFixed(1)}s</strong>
          </div>
          <div>
            <span className="text-slate-400">Altitude:</span>{' '}
            <strong className="text-slate-200">{selectedCapture.alt}m AGL</strong>
          </div>
          <div>
            <span className="text-slate-400">Heading:</span>{' '}
            <strong className="text-slate-200">{selectedCapture.heading}°</strong>
          </div>
          <div className="col-span-2 text-slate-400">
            GPS: <span className="font-mono text-slate-200">{formatLatLon(selectedCapture.lat, selectedCapture.lon)}</span>
          </div>
        </div>

        {/* Synthetic Microclimate Environment Card */}
        <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Thermometer className="w-3.5 h-3.5 text-amber-400" />
              Microclimate Environment
            </span>
            <span className="text-[10px] text-slate-500 italic">Synthetic Spatial Field</span>
          </div>

          <div className="flex justify-around text-center py-1">
            <div>
              <div className="text-sm font-bold text-amber-400">{selectedCapture.temp_c}°C</div>
              <div className="text-[10px] text-slate-400">Canopy Temp</div>
            </div>
            <div className="border-r border-slate-800" />
            <div>
              <div className="text-sm font-bold text-cyan-400">{selectedCapture.rh_pct}%</div>
              <div className="text-[10px] text-slate-400">Rel. Humidity</div>
            </div>
            <div className="border-r border-slate-800" />
            <div>
              <div className="text-sm font-bold text-emerald-400">{selectedCapture.battery_pct}%</div>
              <div className="text-[10px] text-slate-400">UAV Battery</div>
            </div>
          </div>

          {/* Mini Sparkline Chart */}
          {historyData.length > 2 && (
            <div className="h-20 w-full pt-1">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyData}>
                  <Line type="monotone" dataKey="temp" stroke="#f59e0b" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="rh" stroke="#06b6d4" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Prev / Next Stepper */}
      <div className="p-2.5 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between text-xs">
        <button
          onClick={handlePrev}
          disabled={currentIndex <= 0}
          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1 text-slate-300"
        >
          <ChevronLeft className="w-3.5 h-3.5" /> Prev
        </button>
        <span className="text-[11px] text-slate-400">
          {currentIndex + 1} of {recording.captures.length}
        </span>
        <button
          onClick={handleNext}
          disabled={currentIndex >= recording.captures.length - 1}
          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1 text-slate-300"
        >
          Next <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
