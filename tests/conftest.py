"""Pytest configuration and shared fixtures."""

import asyncio
import logging
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import structlog

from core.checkpoints import CheckpointStore
from core.event_store import EventStore
from core.simulation import Simulation
from core.state import SimulationState
from core.time import SimulationClock


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test_strategos.db")


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create a temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return str(checkpoint_dir)


@pytest.fixture
async def event_store(temp_db_path):
    """Create and initialize an event store for testing."""
    store = EventStore(db_path=temp_db_path)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
async def checkpoint_manager(temp_checkpoint_dir):
    """Create a checkpoint store for testing."""
    manager = CheckpointStore(checkpoint_dir=temp_checkpoint_dir, checkpoint_interval=1.0)
    yield manager
    # Cleanup
    shutil.rmtree(temp_checkpoint_dir, ignore_errors=True)


@pytest.fixture
def simulation_clock():
    """Create a simulation clock for testing."""
    return SimulationClock(time_scale=1.0)


@pytest.fixture
def simulation_state():
    """Create a simulation state for testing."""
    return SimulationState(simulation_id=uuid4())


@pytest.fixture
async def simulation(temp_db_path, temp_checkpoint_dir):
    """Create a full simulation instance for testing."""
    sim = Simulation(
        db_path=temp_db_path,
        checkpoint_dir=temp_checkpoint_dir,
        checkpoint_interval=1.0,
    )
    await sim.initialize()
    yield sim
    await sim.shutdown()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
