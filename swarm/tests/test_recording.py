"""Tests for RunRecording serialization, frames, and round-trip load/save."""

from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.main import run_simulation
from agrivyaan_swarm.models.recording import RunRecording


def test_recording_round_trip_json(tmp_path):
    """Verify that a RunRecording serializes and deserializes accurately."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 5
    config.simulation.seed = 42

    recording = run_simulation(config)
    assert len(recording.frames) > 0
    assert len(recording.events) > 0

    save_path = tmp_path / "test_recording.json"
    recording.save_json(save_path)

    reloaded = RunRecording.load_json(save_path)
    assert reloaded.schema_version == recording.schema_version
    assert reloaded.run_id == recording.run_id
    assert reloaded.seed == recording.seed
    assert len(reloaded.frames) == len(recording.frames)
    assert len(reloaded.events) == len(recording.events)
    assert reloaded.completion_state == recording.completion_state
    assert reloaded.metrics["makespan_s"] == recording.metrics["makespan_s"]
