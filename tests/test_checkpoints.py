"""Unit tests for checkpoint management."""

import pytest

from core.state import SimulationState


@pytest.mark.asyncio
async def test_create_checkpoint(checkpoint_manager, simulation_state):
    """Test creating a checkpoint."""
    checkpoint = await checkpoint_manager.create_checkpoint(
        simulation_time=10.0, state=simulation_state, metadata={"test": "checkpoint"}
    )

    assert checkpoint.simulation_time == pytest.approx(10.0)
    assert checkpoint.metadata["test"] == "checkpoint"
    assert len(checkpoint.state_data) > 0


@pytest.mark.asyncio
async def test_restore_checkpoint(checkpoint_manager, simulation_state):
    """Test restoring state from a checkpoint."""
    # Modify state
    simulation_state.current_time = 15.0
    simulation_state.set_custom_state("test_key", "test_value")

    # Create checkpoint
    checkpoint = await checkpoint_manager.create_checkpoint(
        simulation_time=15.0, state=simulation_state
    )

    # Restore state
    restored_state = await checkpoint_manager.restore_checkpoint(checkpoint.checkpoint_id)

    assert restored_state.current_time == pytest.approx(15.0)
    assert restored_state.get_custom_state("test_key") == "test_value"


@pytest.mark.asyncio
async def test_list_checkpoints(checkpoint_manager, simulation_state):
    """Test listing all checkpoints."""
    # Create multiple checkpoints
    for i in range(3):
        await checkpoint_manager.create_checkpoint(
            simulation_time=float(i * 10), state=simulation_state
        )

    checkpoints = await checkpoint_manager.list_checkpoints()
    assert len(checkpoints) == 3

    # Verify ordering
    for i, checkpoint in enumerate(checkpoints):
        assert checkpoint.simulation_time == float(i * 10)


@pytest.mark.asyncio
async def test_get_nearest_checkpoint(checkpoint_manager, simulation_state):
    """Test finding the nearest checkpoint before a given time."""
    # Create checkpoints at times 0, 10, 20, 30
    for i in range(4):
        await checkpoint_manager.create_checkpoint(
            simulation_time=float(i * 10), state=simulation_state
        )

    # Find nearest to time 25
    nearest = await checkpoint_manager.get_nearest_checkpoint(25.0)
    assert nearest is not None
    assert nearest.simulation_time == pytest.approx(20.0)

    # Find nearest to time 5
    nearest = await checkpoint_manager.get_nearest_checkpoint(5.0)
    assert nearest.simulation_time == pytest.approx(0.0)

    # Find nearest to time 100
    nearest = await checkpoint_manager.get_nearest_checkpoint(100.0)
    assert nearest.simulation_time == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_delete_checkpoint(checkpoint_manager, simulation_state):
    """Test deleting a checkpoint."""
    checkpoint = await checkpoint_manager.create_checkpoint(
        simulation_time=10.0, state=simulation_state
    )

    checkpoints = await checkpoint_manager.list_checkpoints()
    assert len(checkpoints) == 1

    await checkpoint_manager.delete_checkpoint(checkpoint.checkpoint_id)

    checkpoints = await checkpoint_manager.list_checkpoints()
    assert len(checkpoints) == 0


@pytest.mark.asyncio
async def test_cleanup_old_checkpoints(checkpoint_manager, simulation_state):
    """Test cleaning up old checkpoints."""
    # Create 15 checkpoints
    for i in range(15):
        await checkpoint_manager.create_checkpoint(simulation_time=float(i), state=simulation_state)

    assert len(await checkpoint_manager.list_checkpoints()) == 15

    # Keep only 5 most recent
    await checkpoint_manager.cleanup_old_checkpoints(keep_count=5)

    checkpoints = await checkpoint_manager.list_checkpoints()
    assert len(checkpoints) == 5

    # Verify we kept the most recent ones (10-14)
    for i, checkpoint in enumerate(checkpoints):
        assert checkpoint.simulation_time == float(10 + i)


@pytest.mark.asyncio
async def test_should_create_checkpoint(checkpoint_manager, simulation_state):
    """Test checkpoint creation interval logic."""
    # Should create first checkpoint
    assert checkpoint_manager.should_create_checkpoint(0.0) is True

    # Create checkpoint at time 0
    await checkpoint_manager.create_checkpoint(simulation_time=0.0, state=simulation_state)

    # Should not create another immediately (interval is 1.0 from conftest)
    assert checkpoint_manager.should_create_checkpoint(0.5) is False

    # Should create after interval
    assert checkpoint_manager.should_create_checkpoint(1.0) is True
    assert checkpoint_manager.should_create_checkpoint(2.0) is True


@pytest.mark.asyncio
async def test_checkpoint_with_entities(checkpoint_manager, simulation_state):
    """Test checkpoint with entity state."""
    from uuid import uuid4

    # Add entities to state
    entity_id_1 = uuid4()
    entity_id_2 = uuid4()

    simulation_state.add_entity(entity_id_1, {"name": "Unit 1"}, "military")
    simulation_state.add_entity(entity_id_2, {"name": "Unit 2"}, "military")
    simulation_state.update_entity_position(entity_id_1, 10.0, 20.0)

    # Create checkpoint
    checkpoint = await checkpoint_manager.create_checkpoint(
        simulation_time=5.0, state=simulation_state
    )

    # Restore and verify entities
    restored_state = await checkpoint_manager.restore_checkpoint(checkpoint.checkpoint_id)

    assert restored_state.entity_count() == 2
    assert restored_state.get_entity(entity_id_1)["name"] == "Unit 1"
    assert restored_state.get_entity_position(entity_id_1) == (10.0, 20.0, 0.0)
