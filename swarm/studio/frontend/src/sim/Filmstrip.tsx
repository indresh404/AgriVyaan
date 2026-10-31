import React, { useRef, useEffect } from 'react';
import { useSimStore, type SimCapture } from '../store/useSimStore';
import { Camera, Image as ImageIcon, Flame } from 'lucide-react';

export const Filmstrip: React.FC = () => {
  const { recording, currentTime, selectedCapture, setSelectedCapture, setIsInspectorOpen, setCurrentTime } =
    useSimStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  if (!recording) return null;

  // Filter captures taken up to current time
  const capturedSoFar = recording.captures.filter((c) => c.t <= currentTime);

  // Auto-scroll to the right as new captures appear during playback
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [capturedSoFar.length]);

  const handleSelectCapture = (cap: SimCapture) => {
    setSelectedCapture(cap);
    setIsInspectorOpen(true);
    setCurrentTime(cap.t);
  };

  return (
    <div className="bg-slate-900/95 backdrop-blur border border-slate-800 rounded-lg p-2.5 shadow-xl flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs px-1">
        <span className="font-semibold text-slate-300 flex items-center gap-1.5">
          <Camera className="w-3.5 h-3.5 text-teal-400" />
          Optical Footprint Captures ({capturedSoFar.length} / {recording.captures.length})
        </span>
        <span className="text-[10px] text-slate-500 font-mono">Click card to inspect</span>
      </div>

      {capturedSoFar.length === 0 ? (
        <div className="h-20 border border-dashed border-slate-800 rounded flex flex-col items-center justify-center text-slate-500 text-xs">
          <ImageIcon className="w-5 h-5 mb-1 opacity-50" />
          <span>No captures yet. Press play to start survey.</span>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-slate-900"
          style={{ maxHeight: '110px' }}
        >
          {capturedSoFar.map((cap) => {
            const isSelected = selectedCapture?.id === cap.id;
            const hasHotspot = Boolean(cap.hotspot_type);

            return (
              <div
                key={cap.id}
                onClick={() => handleSelectCapture(cap)}
                className={`flex-shrink-0 w-24 h-24 rounded border p-1 cursor-pointer transition-all flex flex-col justify-between group select-none relative overflow-hidden ${
                  isSelected
                    ? 'border-emerald-400 bg-emerald-950/30 ring-1 ring-emerald-400'
                    : 'border-slate-800 bg-slate-950/70 hover:border-slate-600'
                }`}
              >
                {/* Thumbnail Image or Fallback */}
                {cap.thumb_url ? (
                  <img
                    src={cap.thumb_url}
                    alt={cap.label}
                    className="w-full h-12 object-cover rounded bg-black/50"
                  />
                ) : (
                  <div className="w-full h-12 rounded bg-slate-800 flex items-center justify-center text-slate-500 text-[10px]">
                    Grid {cap.cell_id || ''}
                  </div>
                )}

                {/* Hotspot Indicator Badge */}
                {hasHotspot && (
                  <div className="absolute top-1 right-1 bg-rose-600/90 text-white rounded px-1 py-0.5 text-[8px] font-bold flex items-center gap-0.5 shadow">
                    <Flame className="w-2.5 h-2.5" />
                    HOTSPOT
                  </div>
                )}

                {/* Info Footer */}
                <div className="flex items-center justify-between text-[9px] font-mono mt-1 text-slate-400">
                  <span className="text-slate-300">UAV-{cap.drone_id}</span>
                  <span className="text-slate-500">{cap.t.toFixed(0)}s</span>
                </div>

                <div className="text-[8px] truncate text-slate-400 font-mono">
                  {cap.stage === 1 ? 'Stage 1 Survey' : 'Stage 2 Inspect'}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
