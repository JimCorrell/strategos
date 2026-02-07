"""Unit tests for the main simulation orchestrator."""

import asyncio

import pytest

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
