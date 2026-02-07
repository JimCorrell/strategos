"""Unit tests for simulation clock."""

import asyncio

import pytest

from core.time import ClockState, SimulationClock


@pytest.mark.asyncio
async def test_clock_initialization(simulation_clock):
    """Test clock initializes correctly."""
    assert simulation_clock.simulation_time == pytest.approx(0.0)
    assert simulation_clock.time_scale == pytest.approx(1.0)
    assert simulation_clock.state == ClockState.STOPPED


@pytest.mark.asyncio
async def test_clock_start(simulation_clock):
    """Test starting the clock."""
    await simulation_clock.start()
    assert simulation_clock.state == ClockState.RUNNING


@pytest.mark.asyncio
async def test_clock_pause(simulation_clock):
    """Test pausing the clock."""
    await simulation_clock.start()
    await asyncio.sleep(0.05)

    await simulation_clock.pause()
    assert simulation_clock.state == ClockState.PAUSED

    time_at_pause = simulation_clock.get_time()

    # Time should not advance while paused
    await asyncio.sleep(0.05)
    assert abs(simulation_clock.get_time() - time_at_pause) < 0.01


@pytest.mark.asyncio
async def test_clock_resume(simulation_clock):
    """Test resuming the clock."""
    await simulation_clock.start()
    await asyncio.sleep(0.05)

    await simulation_clock.pause()
    paused_time = simulation_clock.get_time()

    await simulation_clock.resume()
    assert simulation_clock.state == ClockState.RUNNING

    await asyncio.sleep(0.05)
    assert simulation_clock.get_time() > paused_time


@pytest.mark.asyncio
async def test_clock_stop(simulation_clock):
    """Test stopping the clock."""
    await simulation_clock.start()
    await asyncio.sleep(0.05)

    await simulation_clock.stop()
    assert simulation_clock.state == ClockState.STOPPED


@pytest.mark.asyncio
async def test_clock_tick(simulation_clock):
    """Test clock tick updates time."""
    await simulation_clock.start()

    time_before = simulation_clock.get_time()
    await asyncio.sleep(0.05)

    time_after = await simulation_clock.tick()
    assert time_after > time_before


@pytest.mark.asyncio
async def test_time_scale(simulation_clock):
    """Test time scale affects time progression."""
    # Test 1x scale
    simulation_clock.time_scale = 1.0
    await simulation_clock.start()
    await asyncio.sleep(0.1)
    time_1x = await simulation_clock.tick()

    await simulation_clock.stop()

    # Test 10x scale
    clock_10x = SimulationClock(time_scale=10.0)
    await clock_10x.start()
    await asyncio.sleep(0.1)
    time_10x = await clock_10x.tick()

    # 10x should advance more time (with some tolerance)
    assert time_10x > time_1x * 5

    await clock_10x.stop()


@pytest.mark.asyncio
async def test_set_time_scale(simulation_clock):
    """Test changing time scale during simulation."""
    await simulation_clock.start()

    await simulation_clock.set_time_scale(5.0)
    assert simulation_clock.get_time_scale() == pytest.approx(5.0)

    await simulation_clock.set_time_scale(100.0)
    assert simulation_clock.get_time_scale() == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_invalid_time_scale(simulation_clock):
    """Test that invalid time scales are rejected."""
    with pytest.raises(ValueError):
        await simulation_clock.set_time_scale(0.0)

    with pytest.raises(ValueError):
        await simulation_clock.set_time_scale(-1.0)


@pytest.mark.asyncio
async def test_clock_seek(simulation_clock):
    """Test seeking to a specific time."""
    await simulation_clock.start()
    await asyncio.sleep(0.1)

    # Seek to a specific time
    await simulation_clock.seek(50.0)
    assert simulation_clock.get_time() == pytest.approx(50.0)

    # Seek backward
    await simulation_clock.seek(10.0)
    assert simulation_clock.get_time() == pytest.approx(10.0)

    # Seek to negative (should clamp to 0)
    await simulation_clock.seek(-5.0)
    assert simulation_clock.get_time() == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_format_time():
    """Test time formatting."""
    clock = SimulationClock()

    # Test zero time
    clock.simulation_time = 0.0
    assert clock.format_time() == "00:00:00"

    # Test hours, minutes, seconds
    clock.simulation_time = 3661.0  # 1 hour, 1 minute, 1 second
    assert clock.format_time() == "01:01:01"

    # Test days
    clock.simulation_time = 86400.0 + 3661.0  # 1 day + 1:01:01
    formatted = clock.format_time()
    assert "1d" in formatted


@pytest.mark.asyncio
async def test_get_methods(simulation_clock):
    """Test getter methods."""
    await simulation_clock.start()

    assert simulation_clock.get_state() == ClockState.RUNNING
    assert simulation_clock.get_time() >= 0.0
    assert simulation_clock.get_time_scale() == pytest.approx(1.0)

    await simulation_clock.pause()
    assert simulation_clock.get_state() == ClockState.PAUSED
