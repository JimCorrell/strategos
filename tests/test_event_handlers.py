"""Tests for EventHandlerRegistry."""

import pytest

from core.event_handlers import EventHandlerRegistry
from core.events import Event, EventType
from core.exceptions import HandlerExecutionError


@pytest.fixture
def registry():
    """Create a fresh EventHandlerRegistry for each test."""
    return EventHandlerRegistry()


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        event_type=EventType.MARKER_CREATED,
        simulation_time=1.0,
        data={"label": "Test Marker"},
    )


class TestEventHandlerRegistry:
    """Test EventHandlerRegistry functionality."""

    @pytest.mark.asyncio
    async def test_register_handler(self, registry):
        """Handlers can be registered for specific event types."""
        calls = []

        async def handler(event):
            calls.append(event)

        registry.on(EventType.MARKER_CREATED, handler)

        assert registry.get_handler_count(EventType.MARKER_CREATED) == 1
        assert registry.get_handler_count() == 1

    @pytest.mark.asyncio
    async def test_dispatch_to_specific_handler(self, registry, sample_event):
        """Events are dispatched to handlers registered for that type."""
        marker_calls = []
        entity_calls = []

        async def marker_handler(event):
            marker_calls.append(event)

        async def entity_handler(event):
            entity_calls.append(event)

        registry.on(EventType.MARKER_CREATED, marker_handler)
        registry.on(EventType.ENTITY_CREATED, entity_handler)

        await registry.dispatch(sample_event)

        # Only marker handler should be called
        assert len(marker_calls) == 1
        assert len(entity_calls) == 0
        assert marker_calls[0] == sample_event

    @pytest.mark.asyncio
    async def test_multiple_handlers_for_same_type(self, registry, sample_event):
        """Multiple handlers can be registered for the same event type."""
        calls1 = []
        calls2 = []

        async def handler1(event):
            calls1.append(event)

        async def handler2(event):
            calls2.append(event)

        registry.on(EventType.MARKER_CREATED, handler1)
        registry.on(EventType.MARKER_CREATED, handler2)

        await registry.dispatch(sample_event)

        # Both handlers should be called
        assert len(calls1) == 1
        assert len(calls2) == 1

    @pytest.mark.asyncio
    async def test_wildcard_handler(self, registry, sample_event):
        """Wildcard handlers receive all events."""
        wildcard_calls = []

        async def wildcard_handler(event):
            wildcard_calls.append(event)

        registry.on_all(wildcard_handler)

        # Create events of different types
        marker_event = Event(event_type=EventType.MARKER_CREATED, data={"label": "A"})
        entity_event = Event(event_type=EventType.ENTITY_CREATED, data={"entity_id": "1", "type": "unit"})

        await registry.dispatch(marker_event)
        await registry.dispatch(entity_event)

        # Wildcard handler should receive both
        assert len(wildcard_calls) == 2

    @pytest.mark.asyncio
    async def test_specific_and_wildcard_handlers(self, registry):
        """Both specific and wildcard handlers are called."""
        specific_calls = []
        wildcard_calls = []

        async def specific_handler(event):
            specific_calls.append(event)

        async def wildcard_handler(event):
            wildcard_calls.append(event)

        registry.on(EventType.MARKER_CREATED, specific_handler)
        registry.on_all(wildcard_handler)

        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})
        await registry.dispatch(event)

        # Both should be called
        assert len(specific_calls) == 1
        assert len(wildcard_calls) == 1

    @pytest.mark.asyncio
    async def test_unregister_handler(self, registry):
        """Handlers can be unregistered."""
        calls = []

        async def handler(event):
            calls.append(event)

        registry.on(EventType.MARKER_CREATED, handler)
        result = registry.off(EventType.MARKER_CREATED, handler)

        assert result is True
        assert registry.get_handler_count(EventType.MARKER_CREATED) == 0

        # Dispatch should not call the handler
        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})
        await registry.dispatch(event)

        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_handler(self, registry):
        """Unregistering non-existent handler returns False."""
        async def handler(event):
            pass

        result = registry.off(EventType.MARKER_CREATED, handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_wildcard_handler(self, registry):
        """Wildcard handlers can be unregistered."""
        calls = []

        async def handler(event):
            calls.append(event)

        registry.on_all(handler)
        result = registry.off_all(handler)

        assert result is True

        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})
        await registry.dispatch(event)

        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_handler_error_fail_fast_true(self, registry):
        """With fail_fast=True, handler errors raise immediately."""
        async def failing_handler(event):
            raise ValueError("Handler failed")

        registry.on(EventType.MARKER_CREATED, failing_handler)

        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})

        with pytest.raises(HandlerExecutionError) as exc_info:
            await registry.dispatch(event, fail_fast=True)

        assert "Handler failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handler_error_fail_fast_false(self, registry):
        """With fail_fast=False, handler errors are logged but don't raise."""
        error_count = 0
        success_count = 0

        async def failing_handler(event):
            nonlocal error_count
            error_count += 1
            raise ValueError("Handler failed")

        async def success_handler(event):
            nonlocal success_count
            success_count += 1

        registry.on(EventType.MARKER_CREATED, failing_handler)
        registry.on(EventType.MARKER_CREATED, success_handler)

        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})

        # Should not raise
        await registry.dispatch(event, fail_fast=False)

        # Both handlers should have been called
        assert error_count == 1
        assert success_count == 1

    @pytest.mark.asyncio
    async def test_dispatch_with_no_handlers(self, registry):
        """Dispatching with no handlers doesn't error."""
        event = Event(event_type=EventType.MARKER_CREATED, data={"label": "Test"})

        # Should not raise
        await registry.dispatch(event)

    @pytest.mark.asyncio
    async def test_get_handler_count(self, registry):
        """get_handler_count() returns correct counts."""
        async def handler1(event):
            pass

        async def handler2(event):
            pass

        registry.on(EventType.MARKER_CREATED, handler1)
        registry.on(EventType.MARKER_CREATED, handler2)
        registry.on(EventType.ENTITY_CREATED, handler1)
        registry.on_all(handler2)

        # 2 handlers for MARKER_CREATED
        assert registry.get_handler_count(EventType.MARKER_CREATED) == 2

        # 1 handler for ENTITY_CREATED
        assert registry.get_handler_count(EventType.ENTITY_CREATED) == 1

        # Total: 3 specific + 1 wildcard = 4
        assert registry.get_handler_count() == 4

    @pytest.mark.asyncio
    async def test_clear_handlers(self, registry):
        """clear() removes all handlers."""
        async def handler(event):
            pass

        registry.on(EventType.MARKER_CREATED, handler)
        registry.on_all(handler)

        assert registry.get_handler_count() > 0

        registry.clear()

        assert registry.get_handler_count() == 0

    @pytest.mark.asyncio
    async def test_handler_receives_correct_event(self, registry):
        """Handlers receive the exact event that was dispatched."""
        received_event = None

        async def handler(event):
            nonlocal received_event
            received_event = event

        registry.on(EventType.MARKER_CREATED, handler)

        original_event = Event(
            event_type=EventType.MARKER_CREATED,
            simulation_time=42.0,
            data={"label": "Test", "metadata": {"key": "value"}},
        )

        await registry.dispatch(original_event)

        assert received_event is original_event
        assert received_event.simulation_time == 42.0
        assert received_event.data["label"] == "Test"

    @pytest.mark.asyncio
    async def test_string_event_type_registration(self, registry):
        """Handlers can be registered with string event types."""
        calls = []

        async def handler(event):
            calls.append(event)

        # Register with string
        registry.on("custom.event.type", handler)

        # Dispatch with matching string
        event = Event(event_type="custom.event.type", data={})
        await registry.dispatch(event)

        assert len(calls) == 1
