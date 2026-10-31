import React from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { BatteryCharging, Shield, Plus, Trash2, Cpu } from 'lucide-react';

export const Step6Drones: React.FC = () => {
  const { drones, updateDroneList } = useProjectStore();

  const handleToggleBackup = (droneId: number) => {
    const updated = drones.map((d) => (d.drone_id === droneId ? { ...d, is_backup: !d.is_backup } : d));
    updateDroneList(updated);
  };

  const handleUpdateCharge = (droneId: number, pct: number) => {
    const updated = drones.map((d) => (d.drone_id === droneId ? { ...d, initial_charge_pct: pct } : d));
    updateDroneList(updated);
  };

  const handleAddDrone = () => {
    if (drones.length >= 4) return;
    const newId = drones.length + 1;
    const newDrone = {
      drone_id: newId,
      is_backup: newId === 3,
      capacity_Wh: 74.0,
      power_hover_W: 150.0,
      power_cruise_W: 160.0,
      power_climb_W: 220.0,
      reserve_pct: 25.0,
      initial_charge_pct: 100.0,
      drain_multiplier: 1.0,
    };
    updateDroneList([...drones, newDrone]);
  };

  const handleRemoveDrone = (droneId: number) => {
    if (drones.length <= 1) return;
    updateDroneList(drones.filter((d) => d.drone_id !== droneId));
  };

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Step 6: Fleet Sizing & Battery Models
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Configure UAV fleet (1-4 drones), backup units, and battery parameters (assumed, not measured).
          </p>
        </div>
        {drones.length < 4 && (
          <button
            onClick={handleAddDrone}
            className="bg-cyan-700 hover:bg-cyan-600 text-white text-xs font-semibold px-2.5 py-1 rounded flex items-center gap-1 transition"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Drone
          </button>
        )}
      </div>

      <div className="space-y-2.5">
        {drones.map((d) => (
          <div
            key={d.drone_id}
            className={`border rounded-lg p-3 text-xs transition-all ${
              d.is_backup
                ? 'bg-purple-950/30 border-purple-800'
                : 'bg-slate-900 border-slate-700'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-slate-100">
                <span className={`w-2.5 h-2.5 rounded-full ${d.is_backup ? 'bg-purple-400' : 'bg-cyan-400'}`} />
                <span>Drone {d.drone_id}</span>
                {d.is_backup && (
                  <span className="text-[10px] bg-purple-900/60 text-purple-300 border border-purple-700 px-1.5 py-0.2 rounded font-normal flex items-center gap-1">
                    <Shield className="w-3 h-3" /> Backup (Standby at Base)
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1 text-[11px] text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={d.is_backup}
                    onChange={() => handleToggleBackup(d.drone_id)}
                    className="rounded bg-slate-950 border-slate-700"
                  />
                  <span>Backup Mode</span>
                </label>
                {drones.length > 1 && (
                  <button
                    onClick={() => handleRemoveDrone(d.drone_id)}
                    className="text-slate-500 hover:text-red-400 p-0.5"
                    title="Remove drone"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5 mt-2.5 pt-2 border-t border-slate-800 text-[11px]">
              <div>
                <div className="flex justify-between text-slate-400">
                  <span>Initial Charge</span>
                  <span className="font-mono text-cyan-300 font-semibold">{d.initial_charge_pct}%</span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="100"
                  step="5"
                  value={d.initial_charge_pct}
                  onChange={(e) => handleUpdateCharge(d.drone_id, parseFloat(e.target.value))}
                  className="w-full mt-1"
                />
                <span className="text-[10px] text-slate-500 italic">
                  Tip: Set below 35% to force low-battery handover demo
                </span>
              </div>

              <div className="space-y-1 text-slate-400">
                <div className="flex justify-between">
                  <span>Capacity:</span>
                  <span className="text-slate-200 font-mono">{d.capacity_Wh} Wh</span>
                </div>
                <div className="flex justify-between">
                  <span>Cruise Power:</span>
                  <span className="text-slate-200 font-mono">{d.power_cruise_W} W</span>
                </div>
                <div className="flex justify-between">
                  <span>Safe Reserve:</span>
                  <span className="text-slate-200 font-mono">{d.reserve_pct}%</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded p-2.5 text-xs text-slate-400">
        ⚡ <strong>Low-Battery Handover:</strong> When an active UAV's battery drops near the safety reserve, it aborts, returns to base, and the standby backup UAV takes over the remaining cells.
      </div>
    </div>
  );
};
