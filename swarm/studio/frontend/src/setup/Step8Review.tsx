import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { useSimStore } from '../store/useSimStore';
import { formatArea, formatDistance, formatDuration, formatGSD } from '../lib/format';
import { runSimulation, fetchRecording } from '../api/client';
import { Rocket, CheckCircle, AlertTriangle, ShieldCheck } from 'lucide-react';

export const Step8Review: React.FC = () => {
  const { project, field, camera, drones, hotspots, preview, validation, setScreen } = useProjectStore();
  const { setRecording } = useSimStore();
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const areaInfo = formatArea(field?.area_m2 || 0);

  const handleLaunchSimulation = async () => {
    if (!project) return;
    setIsLaunching(true);
    setLaunchError(null);
    try {
      const res = await runSimulation(project.id, 42);
      const rec = await fetchRecording(res.run_id);
      setRecording(rec);
      setScreen('sim');
    } catch (e: any) {
      setLaunchError(e.message || 'Failed to start simulation');
      setIsLaunching(false);
    }
  };

  const isReady = validation?.is_valid ?? false;

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Rocket className="w-5 h-5 text-emerald-400" />
          Step 8: Mission Review & Launch Simulation
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Final pre-flight checklist. Review survey geometry and launch the multi-UAV precision execution.
        </p>
      </div>

      {/* Summary Matrix */}
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 space-y-2 text-xs">
        <div className="font-bold text-slate-200 border-b border-slate-800 pb-1.5 flex justify-between items-center">
          <span>Mission Specifications</span>
          <span className="text-emerald-400 font-mono text-[11px]">Ready for Execution</span>
        </div>

        <div className="grid grid-cols-2 gap-y-1.5 gap-x-3 text-[11px]">
          <div className="text-slate-400">Field Survey Area:</div>
          <div className="text-slate-200 font-semibold text-right">
            {areaInfo.m2} ({areaInfo.ha})
          </div>

          <div className="text-slate-400">Grid Cell Side & Count:</div>
          <div className="text-slate-200 font-semibold text-right">
            {preview?.grid.cell_side_m}m • {preview?.grid.kept_cells} Cells
          </div>

          <div className="text-slate-400">Survey Altitude & GSD:</div>
          <div className="text-slate-200 font-semibold text-right">
            {camera.altitude_survey_m}m • {formatGSD(preview?.footprint.gsd_mm_per_px || 3.75)}
          </div>

          <div className="text-slate-400">Total UAV Fleet:</div>
          <div className="text-slate-200 font-semibold text-right">
            {drones.filter((d) => !d.is_backup).length} Active + {drones.filter((d) => d.is_backup).length} Backup
          </div>

          <div className="text-slate-400">Target Hotspots:</div>
          <div className="text-slate-200 font-semibold text-right">
            {hotspots.length} Ground-Truth Zones
          </div>

          <div className="text-slate-400">Estimated Mission Time:</div>
          <div className="text-slate-200 font-semibold text-right">
            {formatDuration(
              Math.max(...(preview?.drone_evaluations?.map((e) => e.total_time_s) || [0]))
            )}
          </div>
        </div>
      </div>

      {launchError && (
        <div className="bg-red-950/80 border border-red-500 rounded p-2.5 text-xs text-red-200 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span>{launchError}</span>
        </div>
      )}

      {/* Start Button */}
      <button
        onClick={handleLaunchSimulation}
        disabled={isLaunching || !isReady}
        className={`w-full py-2.5 px-4 rounded font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg ${
          isReady
            ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-950/50'
            : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
        }`}
      >
        <Rocket className="w-4 h-4" />
        {isLaunching ? 'Computing Mission Kinematics...' : isReady ? 'Start Swarm Simulation' : 'Validate Plan in Step 7 First'}
      </button>

      <div className="bg-slate-900/60 border border-slate-800 rounded p-2.5 text-[11px] text-slate-400">
        ℹ️ <strong>Honesty Statement:</strong> Simulation prototype. Detections are the areas you marked, not AI results. Temperature and humidity are synthetic. Battery and time come from a physics model, not measured flight data.
      </div>
    </div>
  );
};
