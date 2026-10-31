"""Public high-level simulation API."""

from __future__ import annotations

import uuid
from typing import Optional
from agrivyaan_swarm.allocation.greedy_allocator import GreedyAllocator
from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.environment.field_generator import generate_scenario
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.recording import RunRecording
from agrivyaan_swarm.simulation.engine import SimulationEngine


def run_simulation(
    config: SimulationConfig,
    field: Optional[Field] = None,
    run_id: Optional[str] = None,
) -> RunRecording:
    """Run an end-to-end swarm simulation based on configuration.

    Args:
        config: Validated SimulationConfig instance.
        field: Optional custom Field. If None, generated deterministically from config.
        run_id: Optional identifier string. Defaults to auto-generated UUID.

    Returns:
        RunRecording instance containing all frames, events, metrics, and completion state.
    """
    config.validate()

    if field is None:
        field = generate_scenario(config)

    if run_id is None:
        run_id = f"run_{uuid.uuid4().hex[:8]}"

    allocator = GreedyAllocator()
    engine = SimulationEngine(
        config=config,
        field=field,
        allocator=allocator,
        run_id=run_id,
    )

    return engine.run()
