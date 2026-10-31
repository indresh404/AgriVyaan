"""Multi-drone scaling and resilience comparison experiment across paired seeds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agrivyaan_swarm.config import FailureConfig, FailureTrigger, load_config
from agrivyaan_swarm.main import run_simulation


def run_paired_comparison(
    seeds_count: int = 20,
    base_config_path: str = "config/default.json",
    output_dir: str = "data/results/comparison",
) -> pd.DataFrame:
    """Run 1, 2, and 3 drone simulations across paired seeds and conditions.

    Conditions evaluated:
        1. Nominal (ample energy, no failures)
        2. Energy-Constrained (capacity = 180 EU, revealing coverage trade-offs)
        3. Hard Failure (Drone 0 stops at t = 30s)
    """
    base_cfg = load_config(base_config_path)
    drone_counts = [1, 2, 3]

    records: List[Dict[str, Any]] = []

    for seed_idx in range(seeds_count):
        current_seed = 42 + seed_idx

        # 1. Nominal condition
        for n_drones in drone_counts:
            cfg = load_config(base_config_path)
            cfg.drones.count = n_drones
            cfg.simulation.seed = current_seed
            cfg.failures = []

            rec = run_simulation(cfg, run_id=f"comp_nominal_d{n_drones}_s{current_seed}")
            m = rec.metrics
            records.append({
                "condition": "Nominal",
                "seed": current_seed,
                "drones": n_drones,
                "makespan_s": m["makespan_s"],
                "total_distance_m": m["total_distance_m"],
                "total_energy_eu": m["total_energy_eu"],
                "energy_per_completed_task_eu": m["energy_per_completed_task_eu"],
                "completed_tasks": m["completed_tasks_count"],
                "coverage": m["priority_weighted_coverage"] if isinstance(m["priority_weighted_coverage"], (int, float)) else 0.0,
                "completion_state": m["completion_state"],
            })

        # 2. Constrained-energy condition
        for n_drones in drone_counts:
            cfg = load_config(base_config_path)
            cfg.drones.count = n_drones
            cfg.drones.energy_capacity_eu = 180.0  # Tight energy limit
            cfg.simulation.seed = current_seed
            cfg.failures = []

            rec = run_simulation(cfg, run_id=f"comp_constrained_d{n_drones}_s{current_seed}")
            m = rec.metrics
            records.append({
                "condition": "Energy-Constrained",
                "seed": current_seed,
                "drones": n_drones,
                "makespan_s": m["makespan_s"],
                "total_distance_m": m["total_distance_m"],
                "total_energy_eu": m["total_energy_eu"],
                "energy_per_completed_task_eu": m["energy_per_completed_task_eu"],
                "completed_tasks": m["completed_tasks_count"],
                "coverage": m["priority_weighted_coverage"] if isinstance(m["priority_weighted_coverage"], (int, float)) else 0.0,
                "completion_state": m["completion_state"],
            })

        # 3. Drone Failure condition (for 2 and 3 drones)
        for n_drones in [2, 3]:
            cfg = load_config(base_config_path)
            cfg.drones.count = n_drones
            cfg.simulation.seed = current_seed
            cfg.failures = [
                FailureConfig(
                    drone_id=0,
                    trigger=FailureTrigger(type="time", t=30.0),
                    kind="HARD_FAILURE",
                    detection_delay_s=5.0,
                )
            ]

            rec = run_simulation(cfg, run_id=f"comp_failure_d{n_drones}_s{current_seed}")
            m = rec.metrics
            records.append({
                "condition": "Hard-Failure-D0",
                "seed": current_seed,
                "drones": n_drones,
                "makespan_s": m["makespan_s"],
                "total_distance_m": m["total_distance_m"],
                "total_energy_eu": m["total_energy_eu"],
                "energy_per_completed_task_eu": m["energy_per_completed_task_eu"],
                "completed_tasks": m["completed_tasks_count"],
                "coverage": m["priority_weighted_coverage"] if isinstance(m["priority_weighted_coverage"], (int, float)) else 0.0,
                "completion_state": m["completion_state"],
            })

    df = pd.DataFrame(records)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    raw_csv = out_path / "raw_comparison_runs.csv"
    df.to_csv(raw_csv, index=False)

    # Compute summary statistics: mean, std, min, max
    summary = df.groupby(["condition", "drones"]).agg(
        makespan_mean=("makespan_s", "mean"),
        makespan_std=("makespan_s", "std"),
        makespan_min=("makespan_s", "min"),
        makespan_max=("makespan_s", "max"),
        energy_mean=("total_energy_eu", "mean"),
        energy_std=("total_energy_eu", "std"),
        coverage_mean=("coverage", "mean"),
        coverage_std=("coverage", "std"),
        completed_mean=("completed_tasks", "mean"),
    ).round(2)

    summary_csv = out_path / "summary_comparison.csv"
    summary.to_csv(summary_csv)

    print("\n" + "=" * 80)
    print("AGRIVYAAN SWARM COMPARISON RESULTS (All metrics computed from actual simulator runs)")
    print("=" * 80)
    print(summary.to_string())
    print("\nObservation note: Increasing drones decreases mission makespan, while total energy")
    print("consumed may increase slightly due to multi-drone travel to/from base.")
    print("-" * 80)
    print(f"Full results saved to: {out_path.resolve()}")
    print("=" * 80 + "\n")

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AgriVyaan Drone Scaling Comparison")
    parser.add_argument("--seeds", type=int, default=20, help="Number of paired seeds to evaluate")
    parser.add_argument("--config", type=str, default="config/default.json", help="Path to default config")
    parser.add_argument("--output-dir", type=str, default="data/results/comparison", help="Output directory")

    args = parser.parse_args()
    run_paired_comparison(seeds_count=args.seeds, base_config_path=args.config, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
