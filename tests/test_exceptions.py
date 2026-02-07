"""Tests for custom exception hierarchy."""

import pytest

from core.exceptions import (
    CheckpointCreationError,
    CheckpointException,
    CheckpointNotFoundError,
    CheckpointRestoreError,
    EventHandlerException,
    EventPersistenceError,
    EventRetrievalError,
    EventStoreException,
    EventValidationError,
    HandlerExecutionError,
    SimulationException,
    SimulationStateError,
    StrategosException,
    TimeSeekError,
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_strategos_exception_is_base(self):
        """StrategosException is the base for all custom exceptions."""
        assert issubclass(EventStoreException, StrategosException)
        assert issubclass(CheckpointException, StrategosException)
        assert issubclass(SimulationException, StrategosException)
        assert issubclass(EventHandlerException, StrategosException)

    def test_event_store_exception_hierarchy(self):
        """EventStore exceptions inherit properly."""
        assert issubclass(EventPersistenceError, EventStoreException)
        assert issubclass(EventRetrievalError, EventStoreException)
        assert issubclass(EventValidationError, EventStoreException)

        # All should inherit from base
        assert issubclass(EventPersistenceError, StrategosException)
        assert issubclass(EventRetrievalError, StrategosException)

    def test_checkpoint_exception_hierarchy(self):
        """Checkpoint exceptions inherit properly."""
        assert issubclass(CheckpointCreationError, CheckpointException)
        assert issubclass(CheckpointRestoreError, CheckpointException)
        assert issubclass(CheckpointNotFoundError, CheckpointException)

        # All should inherit from base
        assert issubclass(CheckpointCreationError, StrategosException)

    def test_simulation_exception_hierarchy(self):
        """Simulation exceptions inherit properly."""
        assert issubclass(SimulationStateError, SimulationException)
        assert issubclass(TimeSeekError, SimulationException)

        # All should inherit from base
        assert issubclass(SimulationStateError, StrategosException)

    def test_event_handler_exception_hierarchy(self):
        """EventHandler exceptions inherit properly."""
        assert issubclass(HandlerExecutionError, EventHandlerException)

        # Should inherit from base
        assert issubclass(HandlerExecutionError, StrategosException)


class TestExceptionUsage:
    """Test that exceptions can be raised and caught properly."""

    def test_raise_event_persistence_error(self):
        """EventPersistenceError can be raised and caught."""
        with pytest.raises(EventPersistenceError) as exc_info:
            raise EventPersistenceError("Failed to persist event")

        assert "Failed to persist event" in str(exc_info.value)

    def test_catch_by_specific_type(self):
        """Exceptions can be caught by their specific type."""
        try:
            raise CheckpointNotFoundError("Checkpoint not found")
        except CheckpointNotFoundError as e:
            assert "Checkpoint not found" in str(e)
        else:
            pytest.fail("Exception not caught")

    def test_catch_by_parent_type(self):
        """Exceptions can be caught by their parent type."""
        try:
            raise EventPersistenceError("Test error")
        except EventStoreException as e:
            assert "Test error" in str(e)
        else:
            pytest.fail("Exception not caught by parent type")

    def test_catch_by_base_type(self):
        """All custom exceptions can be caught by StrategosException."""
        exceptions = [
            EventPersistenceError("Test"),
            CheckpointCreationError("Test"),
            SimulationStateError("Test"),
            HandlerExecutionError("Test"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except StrategosException:
                pass  # Successfully caught
            else:
                pytest.fail(f"{type(exc).__name__} not caught by StrategosException")

    def test_exception_with_context(self):
        """Exceptions can chain with context (from clause)."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise EventPersistenceError("Failed to persist") from e
        except EventPersistenceError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
            assert "Original error" in str(e.__cause__)

    def test_checkpoint_not_found_error(self):
        """CheckpointNotFoundError works correctly."""
        checkpoint_id = "checkpoint_123.pkl"

        with pytest.raises(CheckpointNotFoundError) as exc_info:
            raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

        assert checkpoint_id in str(exc_info.value)

    def test_time_seek_error(self):
        """TimeSeekError works correctly."""
        with pytest.raises(TimeSeekError) as exc_info:
            raise TimeSeekError("Cannot seek to negative time")

        assert "Cannot seek" in str(exc_info.value)

    def test_handler_execution_error(self):
        """HandlerExecutionError works correctly."""
        handler_name = "my_handler"

        with pytest.raises(HandlerExecutionError) as exc_info:
            raise HandlerExecutionError(f"Handler {handler_name} failed")

        assert handler_name in str(exc_info.value)

    def test_simulation_state_error(self):
        """SimulationStateError works correctly."""
        with pytest.raises(SimulationStateError) as exc_info:
            raise SimulationStateError("Simulation already running")

        assert "already running" in str(exc_info.value)


class TestExceptionMessages:
    """Test that exception messages are preserved."""

    def test_simple_message(self):
        """Simple error messages are preserved."""
        msg = "This is a test error"
        exc = EventPersistenceError(msg)

        assert str(exc) == msg

    def test_formatted_message(self):
        """Formatted error messages work correctly."""
        event_id = "abc-123"
        msg = f"Failed to persist event {event_id}: Database error"
        exc = EventPersistenceError(msg)

        assert event_id in str(exc)
        assert "Database error" in str(exc)

    def test_empty_message(self):
        """Exceptions can be raised without messages."""
        exc = StrategosException()
        # Should not raise when converting to string
        str(exc)
