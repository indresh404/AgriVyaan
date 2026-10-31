"""Session state helpers and result loading for Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import streamlit as st
from agrivyaan_swarm.models.recording import RunRecording


def init_session_state() -> None:
    """Initialize default session state keys."""
    if "current_recording" not in st.session_state:
        st.session_state["current_recording"] = None
    if "frame_index" not in st.session_state:
        st.session_state["frame_index"] = 0
    if "comparison_data" not in st.session_state:
        st.session_state["comparison_data"] = None


def get_current_recording() -> Optional[RunRecording]:
    """Retrieve currently loaded RunRecording."""
    return st.session_state.get("current_recording")


def set_current_recording(recording: RunRecording) -> None:
    """Store active RunRecording and reset frame slider."""
    st.session_state["current_recording"] = recording
    st.session_state["frame_index"] = 0


def list_saved_runs(results_dir: str = "data/results") -> List[Path]:
    """List paths to recording.json files in results directory."""
    p = Path(results_dir)
    if not p.exists():
        return []
    return sorted(p.glob("*/recording.json"), key=lambda x: x.stat().st_mtime, reverse=True)


def load_run_by_path(recording_path: Path) -> Optional[RunRecording]:
    """Load a RunRecording from disk and store in session state."""
    try:
        rec = RunRecording.load_json(recording_path)
        set_current_recording(rec)
        return rec
    except Exception as e:
        st.error(f"Failed to load run from {recording_path}: {e}")
        return None
