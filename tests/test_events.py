"""Unit tests for event definitions and types."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from core.events import Event, EventType


def test_event_creation():
    """Test creating a basic event."""
    event = Event(
        event_type=EventType.SIMULATION_STARTED,
        simulation_time=0.0,
        data={"test": "value"},
    )

    assert isinstance(event.event_id, UUID)
    assert event.event_type == EventType.SIMULATION_STARTED
    assert isinstance(event.timestamp, datetime)
    assert event.simulation_time == pytest.approx(0.0)
    assert event.data["test"] == "value"


def test_event_type_enum():
    """Test EventType enum values."""
    assert EventType.SIMULATION_STARTED.value == "simulation.started"
    assert EventType.ENTITY_CREATED.value == "entity.created"
    assert EventType.TIME_SCALE_CHANGED.value == "simulation.time_scale_changed"


def test_event_serialization():
    """Test event to_dict and from_dict."""
    original_event = Event(
        event_id=uuid4(),
        event_type=EventType.ENTITY_CREATED,
        simulation_time=10.5,
        data={"entity_id": "test_123", "type": "unit"},
        metadata={"source": "test"},
    )

    # Convert to dict
    event_dict = original_event.to_dict()

    assert "event_id" in event_dict
    assert event_dict["event_type"] == "entity.created"
    assert event_dict["simulation_time"] == pytest.approx(10.5)
    assert event_dict["data"]["entity_id"] == "test_123"

    # Convert back to Event
    restored_event = Event.from_dict(event_dict)

    assert restored_event.event_id == original_event.event_id
    assert restored_event.event_type == original_event.event_type
    assert restored_event.simulation_time == original_event.simulation_time
    assert restored_event.data == original_event.data
    assert restored_event.metadata == original_event.metadata


def test_event_type_string_conversion():
    """Test that string event types are converted to enums."""
    event = Event(
        event_type="simulation.started",  # Pass as string
        simulation_time=0.0,
    )

    assert isinstance(event.event_type, EventType)
    assert event.event_type == EventType.SIMULATION_STARTED


def test_event_default_values():
    """Test event default values are set correctly."""
    event = Event(event_type=EventType.SIMULATION_STARTED)

    assert isinstance(event.event_id, UUID)
    assert isinstance(event.timestamp, datetime)
    assert event.simulation_time == pytest.approx(0.0)
    assert event.data == {}
    assert event.metadata == {}


def test_all_event_types():
    """Test that all event types can be used."""
    event_types = [
        EventType.SIMULATION_STARTED,
        EventType.SIMULATION_PAUSED,
        EventType.SIMULATION_RESUMED,
        EventType.SIMULATION_STOPPED,
        EventType.TIME_SCALE_CHANGED,
        EventType.ENTITY_CREATED,
        EventType.ENTITY_MOVED,
        EventType.ENTITY_DESTROYED,
        EventType.CHECKPOINT_CREATED,
        EventType.CHECKPOINT_RESTORED,
    ]

    for event_type in event_types:
        event = Event(event_type=event_type, simulation_time=0.0)
        assert event.event_type == event_type
