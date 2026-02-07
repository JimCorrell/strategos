"""Tests for event validation and Event.__hash__."""

import pytest
from uuid import uuid4

from core.events import Event, EventType, EventValidator, EventValidationError


class TestEventHash:
    """Test Event.__hash__ implementation."""

    def test_event_is_hashable(self):
        """Events can be used in sets."""
        event1 = Event(event_type=EventType.MARKER_CREATED, data={"label": "test"})
        event2 = Event(event_type=EventType.MARKER_CREATED, data={"label": "test"})

        # Different events should have different hashes
        assert hash(event1) != hash(event2)

        # Same event should have consistent hash
        assert hash(event1) == hash(event1)

    def test_events_in_set(self):
        """Events can be stored in a set."""
        event1 = Event(event_type=EventType.MARKER_CREATED, data={"label": "test1"})
        event2 = Event(event_type=EventType.MARKER_CREATED, data={"label": "test2"})
        event3 = event1  # Same reference

        event_set = {event1, event2, event3}

        # Should only have 2 unique events (event1 and event3 are the same)
        assert len(event_set) == 2
        assert event1 in event_set
        assert event2 in event_set

    def test_event_hash_based_on_event_id(self):
        """Hash is based on event_id."""
        event_id = uuid4()
        event = Event(event_type=EventType.MARKER_CREATED, event_id=event_id, data={})

        assert hash(event) == hash(event_id)


class TestEventValidator:
    """Test EventValidator functionality."""

    def test_validate_simulation_started_valid(self):
        """Valid SIMULATION_STARTED event passes validation."""
        event = Event(
            event_type=EventType.SIMULATION_STARTED,
            data={"simulation_id": "test-123", "time_scale": 1.0},
        )

        # Should not raise
        EventValidator.validate(event)

    def test_validate_simulation_started_missing_field(self):
        """SIMULATION_STARTED without required field fails."""
        event = Event(
            event_type=EventType.SIMULATION_STARTED,
            data={"simulation_id": "test-123"},  # Missing time_scale
        )

        with pytest.raises(EventValidationError) as exc_info:
            EventValidator.validate(event)

        assert "missing required field: time_scale" in str(exc_info.value)

    def test_validate_simulation_started_wrong_type(self):
        """SIMULATION_STARTED with wrong field type fails."""
        event = Event(
            event_type=EventType.SIMULATION_STARTED,
            data={"simulation_id": 123, "time_scale": 1.0},  # simulation_id should be str
        )

        with pytest.raises(EventValidationError) as exc_info:
            EventValidator.validate(event)

        assert "wrong type" in str(exc_info.value)

    def test_validate_marker_created_valid(self):
        """Valid MARKER_CREATED event passes validation."""
        event = Event(
            event_type=EventType.MARKER_CREATED,
            data={"label": "Test Marker", "metadata": {"foo": "bar"}},
        )

        EventValidator.validate(event)

    def test_validate_marker_created_missing_label(self):
        """MARKER_CREATED without label fails."""
        event = Event(
            event_type=EventType.MARKER_CREATED,
            data={"metadata": {"foo": "bar"}},
        )

        with pytest.raises(EventValidationError) as exc_info:
            EventValidator.validate(event)

        assert "missing required field: label" in str(exc_info.value)

    def test_validate_entity_created_valid(self):
        """Valid ENTITY_CREATED event passes validation."""
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            data={
                "entity_id": "unit_001",
                "type": "infantry",
                "position": [0.0, 0.0, 0.0],
            },
        )

        EventValidator.validate(event)

    def test_validate_entity_created_missing_type(self):
        """ENTITY_CREATED without type fails."""
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            data={"entity_id": "unit_001"},
        )

        with pytest.raises(EventValidationError) as exc_info:
            EventValidator.validate(event)

        assert "missing required field: type" in str(exc_info.value)

    def test_validate_unknown_event_type(self):
        """Unknown event types are skipped (no validation)."""
        event = Event(
            event_type="custom.event.type",
            data={},  # No required fields defined
        )

        # Should not raise
        EventValidator.validate(event)

    def test_validate_event_type_without_schema(self):
        """Event types without schema definition are skipped."""
        event = Event(
            event_type=EventType.SIMULATION_RESUMED,  # No schema defined
            data={},
        )

        # Should not raise
        EventValidator.validate(event)

    def test_is_valid_returns_true_for_valid_event(self):
        """is_valid() returns True for valid events."""
        event = Event(
            event_type=EventType.MARKER_CREATED,
            data={"label": "Test"},
        )

        assert EventValidator.is_valid(event) is True

    def test_is_valid_returns_false_for_invalid_event(self):
        """is_valid() returns False for invalid events."""
        event = Event(
            event_type=EventType.MARKER_CREATED,
            data={},  # Missing label
        )

        assert EventValidator.is_valid(event) is False

    def test_validate_time_scaled_valid(self):
        """Valid TIME_SCALED event passes validation."""
        event = Event(
            event_type=EventType.TIME_SCALED,
            data={"old_scale": 1.0, "new_scale": 2.0},
        )

        EventValidator.validate(event)

    def test_validate_time_scaled_accepts_int_and_float(self):
        """TIME_SCALED accepts both int and float for scale values."""
        event1 = Event(
            event_type=EventType.TIME_SCALED,
            data={"old_scale": 1, "new_scale": 2},  # ints
        )

        event2 = Event(
            event_type=EventType.TIME_SCALED,
            data={"old_scale": 1.0, "new_scale": 2.5},  # floats
        )

        EventValidator.validate(event1)
        EventValidator.validate(event2)

    def test_validate_simulation_paused_valid(self):
        """Valid SIMULATION_PAUSED event passes validation."""
        event = Event(
            event_type=EventType.SIMULATION_PAUSED,
            data={"simulation_id": "test-123", "paused_at": 5.0},
        )

        EventValidator.validate(event)
