import React, { useState } from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Route, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { formatDistance, formatDuration } from '../lib/format';

export const Step7Path: React.FC = () => {
  const { preview, validation, fetchPreview, validateCurrentPlan } = useProjectStore();
  const [isValidating, setIsValidating] = useState(false);

  const handleRunValidation = async () => {
    setIsValidating(true);
    await validateCurrentPlan();
    setIsValidating(false);
  };

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Route className="w-5 h-5 text-sky-400" />
            Step 7: Flight Path Planning & Validation
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Boustrophedon serpentine corridors automatically partitioned for balanced mission time.
          </p>
        </div>
        <button
          onClick={fetchPreview}
          className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800"
          title="Refresh plan"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Per-Drone Path & Energy Cards */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Active Drone Workload Partitioning:</label>
        {preview?.drone_evaluations?.map((evalRes) => (
          <div
            key={evalRes.drone_id}
            className="bg-slate-900 border border-slate-700/80 rounded p-2.5 text-xs space-y-1.5"
          >
            <div className="flex justify-between items-center font-bold">
              <span className="text-sky-300">Drone {evalRes.drone_id}</span>
              <span
                className={`text-[11px] font-semibold ${
                  evalRes.is_battery_sufficient ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {evalRes.is_battery_sufficient ? 'Battery OK' : 'Low Battery RTH Expected'}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-300">
              <div>
                <span className="text-slate-500">Distance:</span> {formatDistance(evalRes.path_length_m)}
              </div>
              <div>
                <span className="text-slate-500">Est. Time:</span> {formatDuration(evalRes.total_time_s)}
              </div>
              <div>
                <span className="text-slate-500">Est. Battery:</span> {evalRes.remaining_battery_pct}%
              </div>
            </div>

            <div className="text-[11px] text-slate-400">
              Captures: {evalRes.num_captures} cells • Energy: {evalRes.energy_used_Wh} Wh
            </div>
          </div>
        ))}
      </div>

      {/* Validation Checklist Button & Results */}
      <div className="border-t border-slate-800 pt-3 space-y-2.5">
        <button
          onClick={handleRunValidation}
          disabled={isValidating}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold py-2 px-3 rounded text-xs flex items-center justify-center gap-1.5 transition"
        >
          <CheckCircle className="w-4 h-4" />
          {isValidating ? 'Validating Flight Geometry...' : 'Validate Flight Plan'}
        </button>

        {validation && (
          <div
            className={`border rounded-lg p-3 text-xs space-y-2 ${
              validation.is_valid
                ? 'bg-emerald-950/40 border-emerald-700'
                : 'bg-amber-950/40 border-amber-700'
            }`}
          >
            <div className="font-bold flex items-center justify-between">
              <span className={validation.is_valid ? 'text-emerald-300' : 'text-amber-300'}>
                {validation.is_valid ? '✅ Flight Plan Validated' : '⚠️ Validation Notice'}
              </span>
              <span className="text-[11px] text-slate-400">
                {validation.checks.filter((c) => c.passed).length}/{validation.checks.length} Passed
              </span>
            </div>

            <div className="space-y-1 text-[11px]">
              {validation.checks.map((chk) => (
                <div key={chk.name} className="flex items-start gap-1.5">
                  {chk.passed ? (
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <span className="font-semibold text-slate-200">{chk.name}:</span>{' '}
                    <span className="text-slate-400">{chk.details}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
