"""Unit tests for event store."""

import pytest

from core.events import Event, EventType


@pytest.mark.asyncio
async def test_event_store_initialization(event_store):
    """Test that event store initializes correctly."""
    assert event_store._db is not None


@pytest.mark.asyncio
async def test_append_event(event_store):
    """Test appending events to the store."""
    event = Event(
        event_type=EventType.SIMULATION_STARTED,
        simulation_time=0.0,
        data={"test": "data"},
    )

    await event_store.append(event)

    # Verify event was stored
    count = await event_store.get_event_count()
    assert count == 1


@pytest.mark.asyncio
async def test_get_events(event_store):
    """Test retrieving events from the store."""
    # Add multiple events
    for i in range(5):
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            simulation_time=float(i),
            data={"index": i},
        )
        await event_store.append(event)

    # Get all events
    events = await event_store.get_events()
    assert len(events) == 5

    # Verify ordering
    for i, event in enumerate(events):
        assert event.data["index"] == i


@pytest.mark.asyncio
async def test_get_events_time_filter(event_store):
    """Test filtering events by time range."""
    # Add events at different times
    for i in range(10):
        event = Event(
            event_type=EventType.ENTITY_CREATED,
            simulation_time=float(i),
            data={"time": i},
        )
        await event_store.append(event)

    # Get events in time range
    events = await event_store.get_events(from_time=3.0, to_time=7.0)
    assert len(events) == 5  # Times 3, 4, 5, 6, 7

    for event in events:
        assert 3.0 <= event.simulation_time <= 7.0


@pytest.mark.asyncio
async def test_get_events_type_filter(event_store):
    """Test filtering events by type."""
    # Add different event types
    for i in range(3):
        await event_store.append(
            Event(event_type=EventType.ENTITY_CREATED, simulation_time=float(i))
        )
    for i in range(2):
        await event_store.append(
            Event(event_type=EventType.ENTITY_DESTROYED, simulation_time=float(i + 10))
        )

    # Filter by type
    created_events = await event_store.get_events(event_types=[EventType.ENTITY_CREATED.value])
    assert len(created_events) == 3

    destroyed_events = await event_store.get_events(event_types=[EventType.ENTITY_DESTROYED.value])
    assert len(destroyed_events) == 2


@pytest.mark.asyncio
async def test_stream_events(event_store):
    """Test streaming events from the store."""
    # Add events
    for i in range(5):
        await event_store.append(
            Event(
                event_type=EventType.ENTITY_CREATED,
                simulation_time=float(i),
                data={"index": i},
            )
        )

    # Stream all events
    streamed = []
    async for event in event_store.stream_events(from_time=0.0):
        streamed.append(event)

    assert len(streamed) == 5

    # Stream from midpoint
    streamed_partial = []
    async for event in event_store.stream_events(from_time=2.0):
        streamed_partial.append(event)

    assert len(streamed_partial) == 3  # Events at times 2, 3, 4


@pytest.mark.asyncio
async def test_event_count(event_store):
    """Test event counting."""
    assert await event_store.get_event_count() == 0

    # Add events
    for i in range(10):
        await event_store.append(
            Event(event_type=EventType.ENTITY_CREATED, simulation_time=float(i))
        )

    assert await event_store.get_event_count() == 10


@pytest.mark.asyncio
async def test_clear_events(event_store):
    """Test clearing all events."""
    # Add events
    for i in range(5):
        await event_store.append(
            Event(event_type=EventType.ENTITY_CREATED, simulation_time=float(i))
        )

    assert await event_store.get_event_count() == 5

    # Clear
    await event_store.clear()

    assert await event_store.get_event_count() == 0


@pytest.mark.asyncio
async def test_event_persistence(event_store, temp_db_path):
    """Test that events persist across store instances."""
    # Add events
    event = Event(
        event_type=EventType.SIMULATION_STARTED,
        simulation_time=0.0,
        data={"persistent": True},
    )
    await event_store.append(event)
    event_id = event.event_id

    # Close store
    await event_store.close()

    # Create new store instance with same database
    from core.event_store import EventStore

    new_store = EventStore(db_path=temp_db_path)
    await new_store.initialize()

    # Verify event exists
    events = await new_store.get_events()
    assert len(events) == 1
    assert str(events[0].event_id) == str(event_id)
    assert events[0].data["persistent"] is True

    await new_store.close()
