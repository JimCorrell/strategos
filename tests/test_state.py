"""Unit tests for simulation state."""

from uuid import uuid4

import pytest


def test_state_initialization(simulation_state):
    """Test state initializes correctly."""
    assert simulation_state.current_time == pytest.approx(0.0)
    assert simulation_state.entity_count() == 0


def test_add_entity(simulation_state):
    """Test adding entities to state."""
    entity_id = uuid4()
    entity_data = {"name": "Test Unit", "health": 100}

    simulation_state.add_entity(entity_id, entity_data, "military")

    assert simulation_state.entity_count() == 1
    assert simulation_state.get_entity(entity_id) == entity_data


def test_remove_entity(simulation_state):
    """Test removing entities from state."""
    entity_id = uuid4()
    simulation_state.add_entity(entity_id, {"name": "Unit 1"}, "military")

    assert simulation_state.entity_count() == 1

    simulation_state.remove_entity(entity_id)

    assert simulation_state.entity_count() == 0
    assert simulation_state.get_entity(entity_id) is None


def test_get_entities_by_type(simulation_state):
    """Test getting entities by type."""
    military_1 = uuid4()
    military_2 = uuid4()
    civilian = uuid4()

    simulation_state.add_entity(military_1, {"name": "Tank"}, "military")
    simulation_state.add_entity(military_2, {"name": "Infantry"}, "military")
    simulation_state.add_entity(civilian, {"name": "Truck"}, "civilian")

    military_entities = simulation_state.get_entities_by_type("military")
    assert len(military_entities) == 2
    assert military_1 in military_entities
    assert military_2 in military_entities

    civilian_entities = simulation_state.get_entities_by_type("civilian")
    assert len(civilian_entities) == 1
    assert civilian in civilian_entities


def test_entity_positions(simulation_state):
    """Test entity position tracking."""
    entity_id = uuid4()
    simulation_state.add_entity(entity_id, {"name": "Unit"}, "military")

    # Update position
    simulation_state.update_entity_position(entity_id, 10.5, 20.3, 5.0)

    position = simulation_state.get_entity_position(entity_id)
    assert position == (10.5, 20.3, 5.0)

    # Update again
    simulation_state.update_entity_position(entity_id, 15.0, 25.0)
    position = simulation_state.get_entity_position(entity_id)
    assert position == (15.0, 25.0, 0.0)  # Default z=0


def test_custom_state(simulation_state):
    """Test custom state storage."""
    simulation_state.set_custom_state("score", 1000)
    simulation_state.set_custom_state("level", "hard")

    assert simulation_state.get_custom_state("score") == 1000
    assert simulation_state.get_custom_state("level") == "hard"
    assert simulation_state.get_custom_state("missing", "default") == "default"


def test_clear_state(simulation_state):
    """Test clearing all state."""
    # Add various state
    entity_id = uuid4()
    simulation_state.add_entity(entity_id, {"name": "Unit"}, "military")
    simulation_state.update_entity_position(entity_id, 10.0, 20.0)
    simulation_state.set_custom_state("key", "value")
    simulation_state.current_time = 100.0

    assert simulation_state.entity_count() > 0

    # Clear
    simulation_state.clear()

    assert simulation_state.entity_count() == 0
    assert simulation_state.current_time == pytest.approx(0.0)
    assert simulation_state.get_custom_state("key") is None


def test_entity_removal_cleans_positions(simulation_state):
    """Test that removing an entity also removes its position."""
    entity_id = uuid4()
    simulation_state.add_entity(entity_id, {"name": "Unit"}, "military")
    simulation_state.update_entity_position(entity_id, 10.0, 20.0)

    assert entity_id in simulation_state.entity_positions

    simulation_state.remove_entity(entity_id)

    assert entity_id not in simulation_state.entity_positions


def test_multiple_entity_types(simulation_state):
    """Test managing multiple entity types."""
    types = ["military", "civilian", "building", "resource"]
    entities_by_type = {}

    for entity_type in types:
        for i in range(3):
            entity_id = uuid4()
            simulation_state.add_entity(entity_id, {"index": i}, entity_type)

            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity_id)

    # Verify counts
    assert simulation_state.entity_count() == 12  # 4 types * 3 entities

    for entity_type in types:
        entities = simulation_state.get_entities_by_type(entity_type)
        assert len(entities) == 3


def test_default_position(simulation_state):
    """Test that entities without positions return default (0, 0, 0)."""
    entity_id = uuid4()
    simulation_state.add_entity(entity_id, {"name": "Unit"}, "military")

    # Position not set yet
    position = simulation_state.get_entity_position(entity_id)
    assert position == (0.0, 0.0, 0.0)
