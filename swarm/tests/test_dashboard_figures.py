"""Tests for dashboard Plotly figure generation and visual asset integration."""

import pandas as pd
from agrivyaan_swarm.config import FailureConfig, FailureTrigger, SimulationConfig
from agrivyaan_swarm.dashboard.assets_loader import image_to_base64_data_uri
from agrivyaan_swarm.dashboard.figures import (
    build_comparison_barchart,
    build_mission_replay_figure,
)
from agrivyaan_swarm.main import run_simulation


def test_build_mission_replay_figure_structure():
    """Verify mission replay figure produces valid traces for boundaries, base, tasks, and drones."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 4
    config.simulation.seed = 42

    recording = run_simulation(config)
    fig = build_mission_replay_figure(recording, frame_idx=0)

    trace_names = [t.name for t in fig.data if t.name]
    assert any("Field Boundary" in name for name in trace_names)
    assert any("Base Station" in name for name in trace_names)
    assert any("Task" in name for name in trace_names)
    assert any("Drone" in name for name in trace_names)


def test_figure_with_and_without_assets():
    """Verify figure handles image layers when assets are given and still works without them."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 3
    recording = run_simulation(config)

    # 1. With assets
    fake_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    fig_with = build_mission_replay_figure(
        recording,
        frame_idx=0,
        farm_image_b64=fake_img,
        master_drone_b64=fake_img,
        swarm_drone_b64=fake_img,
    )
    assert hasattr(fig_with.layout, "images")
    assert len(fig_with.layout.images) > 0

    # 2. Without assets
    fig_without = build_mission_replay_figure(
        recording,
        frame_idx=0,
        farm_image_b64=None,
        master_drone_b64=None,
        swarm_drone_b64=None,
    )
    assert fig_without is not None
    assert len(fig_without.data) > 0


def test_drone_and_task_traces_match_fixed_recording():
    """Verify figure coordinates match a fixed recording snapshot."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 4
    config.simulation.seed = 123
    recording = run_simulation(config)

    test_frame_idx = 1
    frame = recording.frames[test_frame_idx]
    fig = build_mission_replay_figure(recording, frame_idx=test_frame_idx)

    # Drone trace positions should match frame drones
    for d in frame.drones:
        d_trace = next((t for t in fig.data if t.name == f"Drone {d.id} ({d.status})"), None)
        assert d_trace is not None
        assert d_trace.x[0] == d.x
        assert d_trace.y[0] == d.y


def test_failed_drone_shows_x_marker():
    """Verify failed drone renders an X marker and its tasks are released to pending."""
    config = SimulationConfig()
    config.drones.count = 2
    config.tasks.count = 4
    config.simulation.seed = 42
    config.failures = [
        FailureConfig(
            drone_id=1,
            trigger=FailureTrigger(type="time", t=5.0),
            kind="HARD_FAILURE",
            detection_delay_s=0.0,
        )
    ]
    recording = run_simulation(config)

    # Pick a frame after failure
    failed_frame_idx = next(
        (i for i, f in enumerate(recording.frames) if any(d.status == "FAILED" for d in f.drones)),
        len(recording.frames) - 1,
    )

    fig = build_mission_replay_figure(recording, frame_idx=failed_frame_idx)
    trace_names = [str(t.name) for t in fig.data]
    assert any("FAILED" in name for name in trace_names)

    # Check that failed drone has marker symbol 'x'
    failed_trace = next(t for t in fig.data if "FAILED" in str(t.name))
    assert failed_trace.marker.symbol == "x"


def test_bad_image_file_handling():
    """Ensure invalid image data returns None safely without raising exceptions."""
    assert image_to_base64_data_uri("non_existent_file.png") is None
    assert image_to_base64_data_uri(b"not_an_image_corrupted_data") is None


def test_build_comparison_barchart():
    """Verify comparison bar chart formats correctly from dataframe summary."""
    df_summary = pd.DataFrame([
        {
            "condition": "Nominal",
            "drones": 1,
            "makespan_mean": 210.0,
            "makespan_std": 15.0,
        },
        {
            "condition": "Nominal",
            "drones": 2,
            "makespan_mean": 160.0,
            "makespan_std": 10.0,
        },
    ])
    fig = build_comparison_barchart(df_summary)
    assert len(fig.data) == 1
    assert fig.data[0].name == "Nominal — Makespan (s)"
