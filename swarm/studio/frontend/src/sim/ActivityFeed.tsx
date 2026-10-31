import React, { useRef, useEffect } from 'react';
import { useSimStore, type SimEvent } from '../store/useSimStore';
import { ListFilter, Zap, AlertTriangle, Eye, ShieldCheck, CheckCircle2, Navigation } from 'lucide-react';

export const ActivityFeed: React.FC = () => {
  const { recording, currentTime, setCurrentTime } = useSimStore();
  const listRef = useRef<HTMLDivElement>(null);

  if (!recording) return null;

  // Active events up to currentTime
  const activeEvents = recording.events.filter((e) => e.t <= currentTime);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [activeEvents.length]);

  const getEventStyle = (type: string) => {
    switch (type) {
      case 'HANDOVER_DISPATCHED':
      case 'HANDOVER_ACK':
        return {
          icon: <Zap className="w-3 h-3 text-amber-400" />,
          badge: 'bg-amber-950/60 border-amber-500/50 text-amber-300',
          dot: 'bg-amber-400',
        };
      case 'HOTSPOT_DISCOVERED':
        return {
          icon: <AlertTriangle className="w-3 h-3 text-rose-400" />,
          badge: 'bg-rose-950/60 border-rose-500/50 text-rose-300',
          dot: 'bg-rose-400',
        };
      case 'STAGE2_START':
      case 'STAGE2_INSPECT':
        return {
          icon: <Eye className="w-3 h-3 text-cyan-400" />,
          badge: 'bg-cyan-950/60 border-cyan-500/50 text-cyan-300',
          dot: 'bg-cyan-400',
        };
      case 'MISSION_COMPLETE':
        return {
          icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
          badge: 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300',
          dot: 'bg-emerald-400',
        };
      case 'LOW_BATTERY_RTH':
        return {
          icon: <Navigation className="w-3 h-3 text-red-400" />,
          badge: 'bg-red-950/60 border-red-500/50 text-red-300',
          dot: 'bg-red-400',
        };
      default:
        return {
          icon: <ShieldCheck className="w-3 h-3 text-indigo-400" />,
          badge: 'bg-indigo-950/60 border-indigo-500/50 text-indigo-300',
          dot: 'bg-indigo-400',
        };
    }
  };

  return (
    <div className="bg-slate-900/95 backdrop-blur border border-slate-800 rounded-lg p-3 shadow-xl flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-2">
        <div className="flex items-center gap-2">
          <ListFilter className="w-4 h-4 text-emerald-400" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wider">Mission Activity Log</h4>
        </div>
        <span className="text-[10px] font-mono text-slate-400">
          {activeEvents.length} / {recording.events.length} events
        </span>
      </div>

      {/* Events Scroll Container */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-slate-900"
        style={{ minHeight: '160px', maxHeight: '340px' }}
      >
        {activeEvents.length === 0 ? (
          <div className="text-center text-slate-500 text-xs py-8">
            Simulation ready. Press Play to stream live coordination events.
          </div>
        ) : (
          activeEvents.map((evt: SimEvent, idx: number) => {
            const style = getEventStyle(evt.type);
            return (
              <div
                key={idx}
                onClick={() => setCurrentTime(evt.t)}
                className="group p-2 rounded bg-slate-950/60 hover:bg-slate-800/80 border border-slate-800/80 hover:border-slate-700 transition-all cursor-pointer flex flex-col gap-1"
              >
                <div className="flex items-center justify-between text-[10px]">
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                    <span className="text-slate-400 font-bold">{evt.t.toFixed(1)}s</span>
                    {evt.drone_id !== undefined && (
                      <span className="text-slate-300 bg-slate-800 px-1 rounded">
                        UAV-{evt.drone_id}
                      </span>
                    )}
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${style.badge}`}>
                    {evt.type.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="text-[11px] text-slate-300 group-hover:text-white leading-relaxed pl-3 border-l border-slate-800">
                  {evt.detail}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
