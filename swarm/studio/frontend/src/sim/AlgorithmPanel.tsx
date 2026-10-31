import React, { useState } from 'react';
import { useSimStore } from '../store/useSimStore';
import { useProjectStore } from '../store/useProjectStore';
import { formatGSD, formatEnergy } from '../lib/format';
import { Cpu, Scale, CheckCircle, XCircle, ChevronDown, ChevronUp, Activity } from 'lucide-react';

export const AlgorithmPanel: React.FC = () => {
  const { recording, currentTime } = useSimStore();
  const { camera, preview } = useProjectStore();
  const [activeTab, setActiveTab] = useState<'handover' | 'optics' | 'energy'>('handover');

  if (!recording) return null;

  // Find decisions that occurred up to currentTime
  const relevantDecisions = recording.decisions.filter((d) => d.t <= currentTime);
  const latestDecision = relevantDecisions.length > 0 ? relevantDecisions[relevantDecisions.length - 1] : null;

  // Active footprint and GSD formula data
  const altSurvey = camera.altitude_survey_m;
  const fw = (altSurvey * (camera.sensor_w_mm / camera.focal_length_mm)).toFixed(2);
  const fh = (altSurvey * (camera.sensor_h_mm / camera.focal_length_mm)).toFixed(2);
  const gsdVal = (altSurvey * (camera.sensor_w_mm / (camera.focal_length_mm * camera.image_w_px)) * 1000).toFixed(2);

  return (
    <div className="bg-slate-900/95 backdrop-blur border border-slate-800 rounded-lg p-3 shadow-xl flex flex-col h-full text-xs">
      {/* Header Tabs */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2.5">
        <div className="flex items-center gap-1.5 font-bold text-white uppercase tracking-wider text-[11px]">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          Autonomous Dispatch & Logic
        </div>

        <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded border border-slate-800 text-[10px]">
          <button
            onClick={() => setActiveTab('handover')}
            className={`px-2 py-0.5 rounded font-mono transition-colors ${
              activeTab === 'handover' ? 'bg-cyan-600 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Handover
          </button>
          <button
            onClick={() => setActiveTab('optics')}
            className={`px-2 py-0.5 rounded font-mono transition-colors ${
              activeTab === 'optics' ? 'bg-cyan-600 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Optics/GSD
          </button>
          <button
            onClick={() => setActiveTab('energy')}
            className={`px-2 py-0.5 rounded font-mono transition-colors ${
              activeTab === 'energy' ? 'bg-cyan-600 text-white font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Energy Model
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
        {activeTab === 'handover' && (
          <div className="space-y-3">
            <div className="text-[11px] text-slate-300">
              <span className="text-cyan-400 font-semibold">Autonomous Workload Handover Logic:</span>
              <p className="text-slate-400 text-[10px] mt-0.5">
                When an active UAV triggers reserve RTH threshold ($E_{'\text{remain}'} \le E_{'\text{return}'}$),
                unvisited cells are reassigned to either an idle standby backup drone or partitioned across remaining fleet.
              </p>
            </div>

            {latestDecision ? (
              <div className="bg-slate-950/80 border border-slate-800 rounded p-2.5 space-y-2">
                <div className="flex items-center justify-between text-[10px] border-b border-slate-800 pb-1 font-mono">
                  <span className="text-slate-400">Decision Event at {latestDecision.t.toFixed(1)}s</span>
                  <span className="text-amber-400 font-bold">Rule: {latestDecision.rule}</span>
                </div>

                <div className="text-[11px] text-slate-200">
                  <span className="text-slate-400">Trigger UAV:</span>{' '}
                  <span className="font-mono font-bold text-white">UAV-{latestDecision.drone_id}</span>
                </div>

                {/* Candidate Evaluation Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px] font-mono border-collapse text-left">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="py-1">Candidate</th>
                        <th className="py-1">Dist (m)</th>
                        <th className="py-1">Req Wh</th>
                        <th className="py-1">Score</th>
                        <th className="py-1">Feasible</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {latestDecision.candidates.map((cand, idx) => {
                        const isChosen = cand.cluster_id === latestDecision.chosen_cluster_id;
                        return (
                          <tr
                            key={idx}
                            className={`${isChosen ? 'bg-cyan-950/40 text-cyan-200 font-bold' : 'text-slate-400'}`}
                          >
                            <td className="py-1 flex items-center gap-1">
                              {isChosen && <span className="text-cyan-400">▶</span>}
                              {cand.cluster_id}
                            </td>
                            <td className="py-1">{cand.distance_m.toFixed(1)}</td>
                            <td className="py-1">{cand.energy_Wh.toFixed(1)}</td>
                            <td className="py-1">{cand.score.toFixed(2)}</td>
                            <td className="py-1">
                              {cand.feasible ? (
                                <span className="text-emerald-400 flex items-center gap-0.5">
                                  <CheckCircle className="w-2.5 h-2.5" /> Yes
                                </span>
                              ) : (
                                <span className="text-rose-400 flex items-center gap-0.5">
                                  <XCircle className="w-2.5 h-2.5" /> No
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="text-[10px] text-slate-400 bg-slate-900/60 p-2 rounded border border-slate-800">
                  <span className="text-slate-300 font-bold">Dispatcher Reason:</span> {latestDecision.reason}
                </div>
              </div>
            ) : (
              <div className="border border-dashed border-slate-800 rounded p-4 text-center text-slate-500 text-[11px]">
                No handover dispatch triggered yet. If battery drops below RTH threshold during flight, candidate ranking will record here.
              </div>
            )}
          </div>
        )}

        {activeTab === 'optics' && (
          <div className="space-y-2.5">
            <div className="bg-slate-950/80 border border-slate-800 rounded p-2.5 space-y-1.5">
              <span className="text-cyan-400 font-bold text-[10px] uppercase">GSD (Ground Sampling Distance)</span>
              <div className="font-mono text-[10px] text-slate-300 bg-slate-900 p-1.5 rounded">
                GSD = (Altitude × Sensor_w) / (Focal_Length × Image_w) × 1000
              </div>
              <div className="flex justify-between items-center text-[11px] pt-1 border-t border-slate-800">
                <span className="text-slate-400">Live Stage 1 GSD:</span>
                <span className="text-emerald-400 font-mono font-bold">{gsdVal} mm/px</span>
              </div>
            </div>

            <div className="bg-slate-950/80 border border-slate-800 rounded p-2.5 space-y-1.5">
              <span className="text-cyan-400 font-bold text-[10px] uppercase">Ground Optical Footprint</span>
              <div className="font-mono text-[10px] text-slate-300 bg-slate-900 p-1.5 rounded">
                F_w = Altitude × (Sensor_w / f) = {fw} m<br />
                F_h = Altitude × (Sensor_h / f) = {fh} m
              </div>
              <div className="flex justify-between items-center text-[11px] pt-1 border-t border-slate-800">
                <span className="text-slate-400">Sensor Dimensions:</span>
                <span className="text-slate-200 font-mono">
                  {camera.sensor_w_mm} × {camera.sensor_h_mm} mm (f={camera.focal_length_mm}mm)
                </span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'energy' && (
          <div className="space-y-2.5">
            <div className="bg-slate-950/80 border border-slate-800 rounded p-2.5 space-y-1.5">
              <span className="text-cyan-400 font-bold text-[10px] uppercase">Energy Consumption Physics</span>
              <div className="font-mono text-[10px] text-slate-300 bg-slate-900 p-1.5 rounded space-y-1">
                <div>E_segment = (Power_state × Δt) / 3600  [Wh]</div>
                <div>Turn penalty: +2.0s hover time for turns &gt; 30°</div>
              </div>
              <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800">
                Total mission energy derived deterministically from kinematics, climb/descent rate, and hover turn penalties.
              </div>
            </div>

            <div className="bg-slate-950/80 border border-slate-800 rounded p-2.5 space-y-1.5">
              <span className="text-cyan-400 font-bold text-[10px] uppercase">RTH Reserve Safety Condition</span>
              <div className="font-mono text-[10px] text-slate-300 bg-slate-900 p-1.5 rounded">
                E_return = (d_base / v_cruise) × (P_cruise / 3600) + t_desc × (P_climb / 3600) + E_reserve
              </div>
              <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800">
                If current battery ≤ E_return, UAV halts current task, broadcasts handover request to swarm, and initiates direct Return-To-Home.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
