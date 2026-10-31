"""Automated smoke test for the Streamlit dashboard application."""

from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_dashboard_app_smoke():
    """Verify that the Streamlit application starts and renders without exceptions."""
    app_path = Path("src/agrivyaan_swarm/dashboard/app.py").resolve()
    at = AppTest.from_file(str(app_path), default_timeout=30)
    at.run()

    # App should render with no uncaught exceptions
    assert not at.exception, f"App crashed with exception: {at.exception}"

    # Verify key elements rendered
    warning_texts = [w.value for w in at.warning]
    assert any("Simulation only" in text for text in warning_texts)
