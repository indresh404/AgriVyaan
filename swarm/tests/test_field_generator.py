"""Tests for field and task generation."""

import pytest
from agrivyaan_swarm.config import SimulationConfig
from agrivyaan_swarm.environment.field_generator import generate_scenario


def test_field_generator_bounds():
    """Ensure all generated tasks reside strictly within the field boundary."""
    config = SimulationConfig()
    config.field.width_m = 120.0
    config.field.height_m = 80.0
    config.tasks.count = 25
    config.simulation.seed = 123

    field = generate_scenario(config)

    assert len(field.tasks) == 25
    for task in field.tasks:
        x, y = task.position
        assert 0.0 <= x <= 120.0
        assert 0.0 <= y <= 80.0
        assert 0.0 <= task.priority <= 1.0
        assert 0.0 <= task.uncertainty <= 1.0
        assert 0.0 <= task.expected_gain <= 1.0
        assert task.duration_s >= config.tasks.duration_s[0]
        assert task.duration_s <= config.tasks.duration_s[1]


def test_field_generator_deterministic():
    """Verify same seed produces identical tasks."""
    config1 = SimulationConfig()
    config1.simulation.seed = 999
    field1 = generate_scenario(config1)

    config2 = SimulationConfig()
    config2.simulation.seed = 999
    field2 = generate_scenario(config2)

    assert len(field1.tasks) == len(field2.tasks)
    for t1, t2 in zip(field1.tasks, field2.tasks):
        assert t1.id == t2.id
        assert t1.position == t2.position
        assert t1.priority == t2.priority
        assert t1.duration_s == t2.duration_s
