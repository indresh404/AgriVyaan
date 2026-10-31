import React from 'react';
import { useSimStore } from '../store/useSimStore';
import { formatDuration } from '../lib/format';
import { ChevronLeft, ChevronRight, Flag, AlertTriangle, Eye, Zap } from 'lucide-react';

export const Timeline: React.FC = () => {
  const { recording, currentTime, setCurrentTime, jumpToNextEvent, jumpToPrevEvent } = useSimStore();

  if (!recording) return null;

  const totalTime = recording.summary.total_time_s || 1;
  const progressPct = (currentTime / totalTime) * 100;

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'HANDOVER_DISPATCHED':
      case 'HANDOVER_ACK':
        return <Zap className="w-2.5 h-2.5 text-amber-400" />;
      case 'HOTSPOT_DISCOVERED':
        return <AlertTriangle className="w-2.5 h-2.5 text-rose-400" />;
      case 'STAGE2_START':
      case 'STAGE2_INSPECT':
        return <Eye className="w-2.5 h-2.5 text-cyan-400" />;
      default:
        return <Flag className="w-2.5 h-2.5 text-indigo-400" />;
    }
  };

  return (
    <div className="bg-slate-900/95 backdrop-blur border border-slate-800 rounded-lg p-2.5 shadow-xl flex flex-col gap-2">
      {/* Time Header & Quick Step */}
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 font-mono text-slate-300">
          <span className="text-white font-bold">{formatDuration(currentTime)}</span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400">{formatDuration(totalTime)}</span>
          <span className="text-[10px] text-slate-500 ml-1">({currentTime.toFixed(1)}s)</span>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={jumpToPrevEvent}
            title="Jump to Previous Event"
            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] text-slate-400 px-1">Events ({recording.events.length})</span>
          <button
            onClick={jumpToNextEvent}
            title="Jump to Next Event"
            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Scrub Bar & Event Markers */}
      <div className="relative w-full h-6 flex items-center select-none group">
        {/* Track Background */}
        <div className="absolute left-0 right-0 h-2 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
          {/* Progress Fill */}
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500"
            style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
          />
        </div>

        {/* Event Markers on Timeline */}
        {recording.events.map((evt, idx) => {
          const markerPct = (evt.t / totalTime) * 100;
          return (
            <div
              key={idx}
              onClick={(e) => {
                e.stopPropagation();
                setCurrentTime(evt.t);
              }}
              style={{ left: `${markerPct}%` }}
              title={`[${evt.t.toFixed(1)}s] ${evt.detail}`}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-slate-900 border border-slate-600 hover:border-white hover:scale-125 transition-all flex items-center justify-center cursor-pointer z-10"
            >
              {getEventIcon(evt.type)}
            </div>
          );
        })}

        {/* Native Range Scrubber Overlay */}
        <input
          type="range"
          min={0}
          max={totalTime}
          step={0.1}
          value={currentTime}
          onChange={(e) => setCurrentTime(parseFloat(e.target.value))}
          className="absolute inset-0 w-full opacity-0 cursor-ew-resize z-20"
        />
      </div>
    </div>
  );
};
