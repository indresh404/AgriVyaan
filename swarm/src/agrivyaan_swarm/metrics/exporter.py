"""Metrics and event data exporter for JSON and CSV file outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import pandas as pd
from agrivyaan_swarm.models.recording import RunRecording


def export_run_results(recording: RunRecording, output_dir: str | Path) -> Dict[str, Path]:
    """Export RunRecording artifacts (recording.json, metrics.json, metrics.csv, events.csv).

    Returns a dict mapping artifact name to its saved Path.
    """
    out_path = Path(output_dir) / recording.run_id
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. recording.json
    rec_file = out_path / "recording.json"
    recording.save_json(rec_file)

    # 2. metrics.json
    metrics_file = out_path / "metrics.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(recording.metrics, f, indent=2)

    # 3. metrics.csv
    # Flatten metrics dictionary for single-row CSV
    metrics_flat = {}
    for k, v in recording.metrics.items():
        if isinstance(v, list):
            metrics_flat[k] = ";".join(str(item) for item in v)
        else:
            metrics_flat[k] = v

    metrics_df = pd.DataFrame([metrics_flat])
    metrics_csv_file = out_path / "metrics.csv"
    metrics_df.to_csv(metrics_csv_file, index=False)

    # 4. events.csv
    events_data = [
        {
            "t": e.t,
            "type": e.type,
            "drone_id": e.drone_id if e.drone_id is not None else "",
            "task_id": e.task_id if e.task_id is not None else "",
            "detail": e.detail,
        }
        for e in recording.events
    ]
    events_df = pd.DataFrame(events_data)
    events_csv_file = out_path / "events.csv"
    events_df.to_csv(events_csv_file, index=False)

    return {
        "recording_json": rec_file,
        "metrics_json": metrics_file,
        "metrics_csv": metrics_csv_file,
        "events_csv": events_csv_file,
    }
