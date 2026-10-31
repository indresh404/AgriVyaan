import React from 'react';
import { useSimStore } from '../store/useSimStore';
import { interpolateFrames } from '../lib/interpolate';
import { BatteryCharging, Shield, Radio, Navigation } from 'lucide-react';

const DRONE_COLORS: Record<number, string> = {
  1: '#E69F00',
  2: '#56B4E9',
  3: '#009E73',
  4: '#CC79A7',
};

export const DroneCards: React.FC = () => {
  const { recording, currentTime, followDroneId, setFollowDroneId } = useSimStore();

  if (!recording) return null;
  const drones = interpolateFrames(recording.frames, currentTime);

  return (
    <div className="absolute top-16 left-4 z-10 w-64 space-y-2 pointer-events-auto">
      {drones.map((d) => {
        const color = DRONE_COLORS[d.id] || '#38bdf8';
        const isFollowed = followDroneId === d.id;
        const isLowBattery = d.battery_pct < 28.0;

        return (
          <div
            key={d.id}
            onClick={() => setFollowDroneId(isFollowed ? null : d.id)}
            className={`bg-slate-950/90 border rounded-lg p-2.5 text-xs shadow-xl backdrop-blur-md cursor-pointer transition-all ${
              isFollowed ? 'border-sky-400 ring-2 ring-sky-500/30' : 'border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-white">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span>Drone {d.id}</span>
                <span className="text-[10px] font-mono uppercase bg-slate-900 border border-slate-700 px-1.5 py-0.2 rounded text-slate-300">
                  {d.state}
                </span>
              </div>
              <span className={`font-mono font-bold text-xs ${isLowBattery ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`}>
                {d.battery_pct}%
              </span>
            </div>

            {/* Battery bar */}
            <div className="w-full bg-slate-900 rounded-full h-1.5 mt-2 overflow-hidden border border-slate-800">
              <div
                className={`h-full transition-all duration-300 ${
                  isLowBattery ? 'bg-red-500' : d.battery_pct < 45 ? 'bg-amber-400' : 'bg-emerald-400'
                }`}
                style={{ width: `${Math.max(0, Math.min(100, d.battery_pct))}%` }}
              />
            </div>

            <div className="flex justify-between items-center text-[10px] text-slate-400 mt-2 font-mono">
              <span>Alt: {d.alt.toFixed(1)}m</span>
              <span>Hdg: {d.heading.toFixed(0)}°</span>
              <span>{d.target_id ? `Target: ${d.target_id}` : 'Base Launchpad'}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
