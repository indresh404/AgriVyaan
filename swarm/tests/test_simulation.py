"""End-to-end simulation tests and invariant verification across multiple seeds."""

import hashlib
import json
from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.main import run_simulation
from agrivyaan_swarm.models.recording import CompletionState
from agrivyaan_swarm.simulation.movement import step_movement


def test_movement_no_overshoot():
    """Verify kinematics never overshoot the target position."""
    pos = (0.0, 0.0)
    target = (3.0, 4.0)  # distance = 5.0 m
    speed = 10.0  # speed * dt = 10.0 * 1.0 = 10.0 m > 5.0 m
    dt = 1.0

    new_pos, dist_moved, arrived = step_movement(pos, target, speed, dt)
    assert arrived is True
    assert new_pos == target
    assert dist_moved == 5.0


def test_multi_drone_counts_termination():
    """Verify 1, 2, and 3 drone configurations terminate cleanly with valid completion states."""
    for n_drones in (1, 2, 3):
        config = SimulationConfig()
        config.drones.count = n_drones
        config.tasks.count = 6
        config.simulation.seed = 100 + n_drones

        recording = run_simulation(config)
        assert recording.completion_state in (
            CompletionState.COMPLETE,
            CompletionState.INCOMPLETE_UNFINISHED_TASKS,
        )
        assert recording.metrics["makespan_s"] > 0
        assert recording.metrics["duplicate_assignments"] == 0
        assert recording.metrics["battery_reserve_violations"] == 0


def test_invariants_across_multiple_seeds():
    """Ensure zero duplicate assignments and zero battery reserve violations across multiple seeds."""
    seeds = [10, 25, 42, 77, 99]
    for s in seeds:
        config = SimulationConfig()
        config.drones.count = 3
        config.tasks.count = 10
        config.simulation.seed = s

        recording = run_simulation(config)
        assert recording.metrics["duplicate_assignments"] == 0, f"Duplicate assignment detected in seed {s}"
        assert recording.metrics["battery_reserve_violations"] == 0, f"Reserve violation in seed {s}"


def test_identical_seed_reproducibility():
    """Verify identical seed produces identical execution and metrics."""
    config1 = SimulationConfig()
    config1.drones.count = 2
    config1.tasks.count = 8
    config1.simulation.seed = 777

    rec1 = run_simulation(config1, run_id="repro_1")
    rec2 = run_simulation(config1, run_id="repro_1")

    # Serialize frames and metrics to json and compare hash
    json1 = json.dumps(rec1.to_dict(), sort_keys=True)
    json2 = json.dumps(rec2.to_dict(), sort_keys=True)

    hash1 = hashlib.sha256(json1.encode()).hexdigest()
    hash2 = hashlib.sha256(json2.encode()).hexdigest()

    assert hash1 == hash2, "Identical seed must produce bit-for-bit identical RunRecording"
