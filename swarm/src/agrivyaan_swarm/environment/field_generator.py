"""Deterministic scenario and field generator."""

from __future__ import annotations

import numpy as np
from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.models.field import Field
from agrivyaan_swarm.models.task import InspectionTask, TaskStatus


def generate_scenario(config: SimulationConfig) -> Field:
    """Generate a Field instance populated with tasks deterministically from config."""
    rng = np.random.default_rng(config.simulation.seed)

    field = Field(
        width_m=config.field.width_m,
        height_m=config.field.height_m,
        base_position=config.field.base,
        tasks=[],
    )

    tasks_count = config.tasks.count
    if tasks_count == 0:
        return field

    min_dur, max_dur = config.tasks.duration_s
    rate = config.tasks.inspect_rate_eu_per_s

    # Generate task positions inside field boundaries
    xs = rng.uniform(0.0, config.field.width_m, size=tasks_count)
    ys = rng.uniform(0.0, config.field.height_m, size=tasks_count)
    priorities = rng.uniform(0.1, 1.0, size=tasks_count)
    uncertainties = rng.uniform(0.1, 1.0, size=tasks_count)
    gains = rng.uniform(0.1, 1.0, size=tasks_count)
    durations = rng.uniform(min_dur, max_dur, size=tasks_count) if max_dur > min_dur else np.full(tasks_count, min_dur)

    tasks: list[InspectionTask] = []
    for i in range(tasks_count):
        dur = float(round(durations[i], 1))
        energy = float(round(dur * rate, 2))
        task = InspectionTask(
            id=i,
            position=(float(round(xs[i], 2)), float(round(ys[i], 2))),
            priority=float(round(priorities[i], 3)),
            uncertainty=float(round(uncertainties[i], 3)),
            expected_gain=float(round(gains[i], 3)),
            duration_s=dur,
            inspection_energy_eu=energy,
            status=TaskStatus.PENDING,
            assigned_drone_id=None,
            attempts=0,
        )
        tasks.append(task)

    field.tasks = tasks
    return field
