"""Unit tests for the main simulation orchestrator."""

import asyncio

import pytest
import structlog.testing

from core.events import EventType
from core.time import ClockState


@pytest.mark.asyncio
async def test_simulation_initialization(simulation):
    """Test simulation initializes correctly."""
    assert simulation.simulation_id is not None
    assert simulation.clock is not None
    assert simulation.event_store is not None
    assert simulation.checkpoint_manager is not None
    assert simulation.state is not None


@pytest.mark.asyncio
async def test_simulation_start_stop(simulation):
    """Test starting and stopping simulation."""
    await simulation.start()
    assert simulation._running is True
    assert simulation.clock.get_state() == ClockState.RUNNING

    await simulation.stop()
    assert simulation._running is False
    assert simulation.clock.get_state() == ClockState.STOPPED


@pytest.mark.asyncio
async def test_simulation_pause_resume(simulation):
    """Test pausing and resuming simulation."""
    await simulation.start()
    assert simulation._running is True

    await simulation.pause()
    assert simulation._running is False
    assert simulation.clock.get_state() == ClockState.PAUSED

    await simulation.resume()
    assert simulation._running is True
    assert simulation.clock.get_state() == ClockState.RUNNING

    await simulation.stop()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Phase 2: Continuous time progression not yet implemented")
async def test_simulation_time_progression(simulation):
    """Test that simulation time progresses."""
    await simulation.start()

    time_start = simulation.state.current_time
    await asyncio.sleep(0.1)

    time_after = simulation.state.current_time
    assert time_after > time_start

    await simulation.stop()


@pytest.mark.asyncio
async def test_get_status(simulation):
    """Test getting simulation status."""
    status = simulation.get_status()

    assert "simulation_id" in status
    assert "current_time" in status
    assert "formatted_time" in status
    assert "time_scale" in status
    assert "state" in status
    assert "entity_count" in status
    assert "running" in status


@pytest.mark.asyncio
async def test_simulation_with_custom_time_scale(simulation):
    """Test simulation with custom time scale."""
    await simulation.start(time_scale=10.0)

    assert simulation.clock.get_time_scale() == pytest.approx(10.0)

    await simulation.stop()


@pytest.mark.asyncio
async def test_double_start_ignored(simulation):
    """Test that starting an already running simulation is ignored."""
    await simulation.start()
    assert simulation._running is True

    # Try to start again
    await simulation.start()
    assert simulation._running is True  # Still running, no error

    await simulation.stop()


@pytest.mark.asyncio
async def test_pause_when_not_running(simulation):
    """Test that pausing when not running doesn't cause errors."""
    assert simulation._running is False

    await simulation.pause()  # Should not raise error
    assert simulation._running is False


@pytest.mark.asyncio
async def test_shutdown(simulation):
    """Test simulation shutdown."""
    await simulation.start()
    await asyncio.sleep(0.05)

    await simulation.shutdown()

    assert simulation._running is False
    # EventStore should be closed
    assert simulation.event_store._db is None


@pytest.mark.asyncio
async def test_simulation_start_logs_emitted(simulation):
    """Verify simulation.started log is emitted on start."""
    with structlog.testing.capture_logs() as logs:
        await simulation.start()
        await simulation.stop()

    events = [l["event"] for l in logs]
    assert "simulation.started" in events


@pytest.mark.asyncio
async def test_emit_event_logs_emitted(simulation):
    """Verify event.emitting log is emitted when creating a marker."""
    await simulation.start()
    with structlog.testing.capture_logs() as logs:
        await simulation.create_marker("test_marker")

    events = [l["event"] for l in logs]
    assert "event.emitting" in events

    await simulation.stop()


@pytest.mark.asyncio
async def test_seek_logs_emitted(simulation):
    """Verify seek start and completion are logged."""
    await simulation.start()
    await simulation.create_marker("before_seek")
    await simulation.pause()

    with structlog.testing.capture_logs() as logs:
        await simulation.seek(0.0)

    events = [l["event"] for l in logs]
    assert "simulation.seek.started" in events
    assert "simulation.seek.completed" in events


@pytest.mark.asyncio
@pytest.mark.skip(reason="Phase 2: Continuous time progression not yet implemented")
async def test_simulation_loop_running(simulation):
    """Test that simulation loop actually runs."""
    await simulation.start()

    # Simulation should be running and advancing time
    initial_time = simulation.state.current_time
    await asyncio.sleep(0.15)  # Wait for several ticks

    # Time should have advanced
    assert simulation.state.current_time > initial_time

    await simulation.stop()
