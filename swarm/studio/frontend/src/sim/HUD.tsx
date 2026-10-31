import React from 'react';
import { useSimStore } from '../store/useSimStore';
import { useProjectStore } from '../store/useProjectStore';
import { formatDuration } from '../lib/format';
import { Play, Pause, FastForward, RotateCcw, Layers, ArrowLeft, Eye } from 'lucide-react';

const SPEED_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0];

export const HUD: React.FC = () => {
  const { recording, currentTime, isPlaying, playbackSpeed, layers, togglePlay, setPlaybackSpeed, setCurrentTime, toggleLayer } = useSimStore();
  const { setScreen } = useProjectStore();

  const totalTime = recording?.summary.total_time_s || 100.0;
  const progressPct = (currentTime / totalTime) * 100;

  return (
    <div className="absolute top-4 left-4 right-4 z-10 flex items-center justify-between pointer-events-none">
      {/* Left Back & State Badge */}
      <div className="flex items-center gap-2 pointer-events-auto">
        <button
          onClick={() => setScreen('wizard')}
          className="bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 shadow-xl backdrop-blur-md transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Setup Wizard
        </button>
        <div className="bg-slate-900/90 border border-slate-700 rounded-lg px-3 py-1.5 text-xs font-bold text-sky-400 shadow-xl backdrop-blur-md flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>MISSION REPLAY • 60 FPS</span>
        </div>
      </div>

      {/* Center Flight Transport Bar */}
      <div className="bg-slate-950/90 border border-slate-700/80 rounded-xl px-4 py-2 shadow-2xl backdrop-blur-md flex items-center gap-3 pointer-events-auto">
        {/* Play / Pause */}
        <button
          onClick={togglePlay}
          className="w-8 h-8 rounded-full bg-sky-600 hover:bg-sky-500 text-white flex items-center justify-center transition shadow-md shadow-sky-950"
        >
          {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
        </button>

        {/* Reset to 0 */}
        <button
          onClick={() => setCurrentTime(0)}
          className="text-slate-400 hover:text-white p-1"
          title="Restart mission"
        >
          <RotateCcw className="w-4 h-4" />
        </button>

        {/* Time display */}
        <div className="font-mono text-xs font-bold text-slate-200 flex items-center gap-1">
          <span className="text-sky-400">{formatDuration(currentTime)}</span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400">{formatDuration(totalTime)}</span>
        </div>

        {/* Speed Selector */}
        <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded p-0.5 text-[11px]">
          {SPEED_OPTIONS.map((spd) => (
            <button
              key={spd}
              onClick={() => setPlaybackSpeed(spd)}
              className={`px-1.5 py-0.5 rounded font-mono font-medium transition ${
                playbackSpeed === spd ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>

      {/* Right Layer Toggles */}
      <div className="bg-slate-950/90 border border-slate-700/80 rounded-lg p-1.5 shadow-xl backdrop-blur-md flex items-center gap-1.5 pointer-events-auto text-xs">
        <button
          onClick={() => toggleLayer('coverage')}
          className={`px-2 py-1 rounded text-[11px] font-medium transition ${
            layers.coverage ? 'bg-sky-950 text-sky-300 border border-sky-800' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Coverage
        </button>
        <button
          onClick={() => toggleLayer('hotspots')}
          className={`px-2 py-1 rounded text-[11px] font-medium transition ${
            layers.hotspots ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Hotspots
        </button>
      </div>
    </div>
  );
};
