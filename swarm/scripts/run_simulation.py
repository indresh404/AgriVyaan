"""CLI script to execute a single simulation run and export artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to path for direct script execution if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agrivyaan_swarm.config import load_config
from agrivyaan_swarm.main import run_simulation
from agrivyaan_swarm.metrics.exporter import export_run_results
from agrivyaan_swarm.visualization.static_plot import plot_simulation_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AgriVyaan Multi-Drone Simulation")
    parser.add_argument("--config", type=str, default="config/default.json", help="Path to config JSON")
    parser.add_argument("--drones", type=int, default=None, help="Override drone count")
    parser.add_argument("--tasks", type=int, default=None, help="Override task count")
    parser.add_argument("--seed", type=int, default=None, help="Override random seed")
    parser.add_argument("--output-dir", type=str, default="data/results", help="Directory to save run results")
    parser.add_argument("--plot", action="store_true", default=True, help="Save summary plot PNG")

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    if args.drones is not None:
        config.drones.count = args.drones
    if args.tasks is not None:
        config.tasks.count = args.tasks
    if args.seed is not None:
        config.simulation.seed = args.seed

    print(f"Starting AgriVyaan simulation (Drones: {config.drones.count}, Tasks: {config.tasks.count}, Seed: {config.simulation.seed})...")
    recording = run_simulation(config)

    # Export artifacts
    artifacts = export_run_results(recording, args.output_dir)

    # Optional plot export
    if args.plot:
        plot_path = Path(args.output_dir) / recording.run_id / "summary_plot.png"
        plot_simulation_run(recording, output_path=plot_path)
        artifacts["summary_plot"] = plot_path

    m = recording.metrics
    print("\n" + "=" * 50)
    print(f"SIMULATION RUN COMPLETE: {recording.run_id}")
    print("=" * 50)
    print(f"Completion State:           {recording.completion_state.value}")
    print(f"Mission Makespan:           {m.get('makespan_s')} s")
    print(f"Total Distance Travelled:   {m.get('total_distance_m')} m")
    print(f"Total Energy Consumed:      {m.get('total_energy_eu')} EU")
    print(f"Energy Per Completed Task:  {m.get('energy_per_completed_task_eu')} EU/task")
    print(f"Tasks Completed / Total:    {m.get('completed_tasks_count')} / {m.get('total_tasks_count')}")
    print(f"Priority-Weighted Coverage: {m.get('priority_weighted_coverage')}")
    print(f"Duplicate Assignments:      {m.get('duplicate_assignments')} (Invariant: 0)")
    print(f"Battery Reserve Violations: {m.get('battery_reserve_violations')} (Invariant: 0)")
    print("-" * 50)
    print(f"Artifacts saved in: {Path(args.output_dir) / recording.run_id}")
    for k, v in artifacts.items():
        print(f"  - {k}: {v}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
