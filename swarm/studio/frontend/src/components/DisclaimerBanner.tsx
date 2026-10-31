import React, { useState } from 'react';
import { ShieldAlert, ChevronDown, ChevronUp, Info } from 'lucide-react';

export const DisclaimerBanner: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-amber-950/90 border-b border-amber-600/40 text-amber-200 text-xs px-4 py-1.5 transition-all select-none">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className="bg-amber-500/20 border border-amber-400 text-amber-300 px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase flex-shrink-0">
            SIM
          </div>
          <div className="truncate text-[11px] font-medium text-amber-100">
            <strong>Simulation prototype:</strong> Detections are marked synthetic areas, not AI outputs. Temperature & humidity are synthetic. Battery & time come from an abstract model.
          </div>
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1 text-[11px] text-amber-300 hover:text-white underline font-mono flex-shrink-0"
        >
          <span>{isExpanded ? 'Less' : 'Details & Limits'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="max-w-7xl mx-auto mt-2 pt-2 border-t border-amber-800/60 text-[11px] text-amber-200/90 space-y-1.5 pb-1">
          <p>
            <strong>Honesty Statement:</strong> This is a software simulation prototype for precision-agriculture swarm coordination. It does not control real aircraft, does not claim real multi-drone flight or collision avoidance, does not detect real crop pathologies, and does not validate physical battery chemistries.
          </p>
          <p>
            <strong>Known Imagery Limit:</strong> Public satellite imagery (Esri World Imagery) is approximately 0.3–0.6 m/pixel resolution. In this simulator, simulated "detail" captures at 8m altitude zoom into available satellite tiles or user-uploaded samples, and cannot depict true leaf-level microscopic resolution.
          </p>
        </div>
      )}
    </div>
  );
};
