import React, { useEffect, useState } from 'react';
import { useProjectStore } from './store/useProjectStore';
import { useSimStore } from './store/useSimStore';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { Wizard } from './setup/Wizard';
import { SetupMap } from './setup/SetupMap';
import { SimScreen } from './sim/SimScreen';
import { Play, RotateCcw, Sparkles, FolderOpen, Save, Loader2 } from 'lucide-react';

export function App() {
  const { screen, setScreen, project, createDefaultProject, isLoading, error } = useProjectStore();
  const { recording } = useSimStore();

  useEffect(() => {
    // Automatically create or load default demo field if none selected
    if (!project) {
      createDefaultProject();
    }
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* 1. Permanent Simulation Honesty Disclaimer Banner */}
      <DisclaimerBanner />

      {/* 2. Main Screen Switcher */}
      {screen === 'wizard' ? (
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {/* Top Bar for Setup Mode */}
          <header className="h-12 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between z-10 flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-gradient-to-tr from-emerald-500 to-teal-400 rotate-45 shadow-sm shadow-emerald-500/50" />
                <h1 className="text-sm font-extrabold tracking-wider bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent uppercase">
                  AgriVyaan Mission Studio
                </h1>
              </div>
              <span className="text-slate-700">|</span>
              <span className="text-xs text-slate-400 font-mono">
                {project ? project.name : 'Initializing Project...'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {recording && (
                <button
                  onClick={() => setScreen('sim')}
                  className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-lg shadow-sky-950 transition"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Resume Replay</span>
                </button>
              )}
            </div>
          </header>

          {/* Setup Workspace: Wizard on Left, Satellite Map on Right */}
          <div className="flex-1 flex overflow-hidden relative">
            <Wizard />
            <div className="flex-1 relative h-full">
              <SetupMap />
            </div>
          </div>
        </div>
      ) : (
        <SimScreen />
      )}

      {/* Global Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-center gap-3 shadow-2xl">
            <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
            <div className="text-xs font-medium text-slate-300">Synchronizing Mission Geometry...</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
