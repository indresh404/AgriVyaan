import React, { useState } from 'react';
import { useSimStore } from '../store/useSimStore';
import { useProjectStore } from '../store/useProjectStore';
import { MapCanvasLayer } from './MapCanvasLayer';
import { HUD } from './HUD';
import { DroneCards } from './DroneCards';
import { CaptureInspector } from './CaptureInspector';
import { Timeline } from './Timeline';
import { Filmstrip } from './Filmstrip';
import { ActivityFeed } from './ActivityFeed';
import { AlgorithmPanel } from './AlgorithmPanel';
import { PanelRightClose, PanelRightOpen, ArrowLeft, BarChart3 } from 'lucide-react';
import { formatDistance, formatDuration } from '../lib/format';

export const SimScreen: React.FC = () => {
  const { recording } = useSimStore();
  const { setScreen, project } = useProjectStore();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  if (!recording) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-slate-950 text-slate-400 gap-4">
        <p className="text-sm">No simulation recording loaded.</p>
        <button
          onClick={() => setScreen('wizard')}
          className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2"
        >
          <ArrowLeft className="w-4 h-4" /> Return to Mission Setup
        </button>
      </div>
    );
  }

  const { summary } = recording;

  return (
    <div className="h-full flex flex-col bg-slate-950 overflow-hidden relative">
      {/* Top Mission Telemetry Bar */}
      <div className="h-10 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between z-20 flex-shrink-0 text-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setScreen('wizard')}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white font-semibold transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Mission Setup</span>
          </button>
          <span className="text-slate-600">|</span>
          <span className="font-bold text-white tracking-wide truncate max-w-[240px]">
            {project?.name || 'AgriVyaan Precision Survey'}
          </span>
          <span className="text-[10px] font-mono uppercase bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 px-2 py-0.5 rounded">
            Stage 1 & 2 Complete
          </span>
        </div>

        {/* Telemetry KPI Badges */}
        <div className="flex items-center gap-4 text-[11px] font-mono text-slate-300">
          <div>
            <span className="text-slate-500 mr-1.5">Survey Time:</span>
            <span className="text-emerald-400 font-bold">{formatDuration(summary.total_time_s)}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1.5">Distance:</span>
            <span className="text-cyan-400 font-bold">{formatDistance(summary.total_distance_m)}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1.5">Captures:</span>
            <span className="text-white font-bold">{summary.total_captures}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1.5">Handovers:</span>
            <span className="text-amber-400 font-bold">{summary.handovers_count}</span>
          </div>

          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            title={isSidebarOpen ? 'Collapse Ops Panel' : 'Expand Ops Panel'}
            className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition ml-2"
          >
            {isSidebarOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 relative flex overflow-hidden">
        {/* Leaflet Map & Canvas Area */}
        <div className="flex-1 relative h-full">
          {/* Map canvas overlay */}
          <MapCanvasLayer />

          {/* Overlaid UI Controls */}
          <HUD />
          <DroneCards />
          <CaptureInspector />

          {/* Bottom Floating Control Dock */}
          <div className="absolute bottom-4 left-4 right-4 z-10 flex flex-col gap-2 pointer-events-auto max-w-4xl mx-auto">
            <Timeline />
            <Filmstrip />
          </div>
        </div>

        {/* Right Collapsible Mission Ops Dock */}
        {isSidebarOpen && (
          <div className="w-96 border-l border-slate-800 bg-slate-950/95 flex flex-col h-full z-10 shadow-2xl">
            {/* Top: Live Activity Feed */}
            <div className="h-[48%] border-b border-slate-800 p-2 overflow-hidden">
              <ActivityFeed />
            </div>

            {/* Bottom: Autonomous Algorithm & Candidate Table */}
            <div className="flex-1 p-2 overflow-hidden">
              <AlgorithmPanel />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
