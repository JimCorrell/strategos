"""Tests for deterministic movement replay and time travel."""

import asyncio
import tempfile
import shutil
from pathlib import Path

import pytest

from core.simulation import Simulation


@pytest.fixture
async def sim():
    """Create a test simulation."""
    temp_dir = Path(tempfile.mkdtemp())
    db_path = str(temp_dir / "test.db")
    checkpoint_dir = str(temp_dir / "checkpoints")
    Path(checkpoint_dir).mkdir()

    simulation = Simulation(db_path=db_path, checkpoint_dir=checkpoint_dir)
    await simulation.initialize()

    yield simulation

    await simulation.shutdown()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
class TestDeterministicReplay:
    """Test that movement is deterministic on replay."""

    async def test_position_deterministic_on_replay(self, sim):
        """Entity position is same after replaying events."""
        await sim.start()

        # Create entity
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set velocity and wait
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.5)

        # Record position at t=0.5
        time1 = sim.clock.get_time()
        pos1 = sim.get_entity_position(entity_id)

        # Continue simulation
        await asyncio.sleep(0.3)

        # Rewind to t=0.5
        await sim.seek(time1)

        # Position should match recorded position
        pos2 = sim.get_entity_position(entity_id)

        assert pos1 is not None
        assert pos2 is not None

        # Should be very close (within floating point precision)
        assert abs(pos1[0] - pos2[0]) < 0.01
        assert abs(pos1[1] - pos2[1]) < 0.01
        assert abs(pos1[2] - pos2[2]) < 0.01

    async def test_velocity_change_replays_correctly(self, sim):
        """Velocity changes replay correctly."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Move at 10 m/s
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.3)

        # Change to 20 m/s
        await sim.set_entity_velocity(entity_id, velocity=(20.0, 0.0, 0.0))
        await asyncio.sleep(0.3)

        # Record final position
        final_time = sim.clock.get_time()
        final_pos = sim.get_entity_position(entity_id)

        # Rewind to start
        await sim.seek(0.0)

        # Fast-forward to final time
        await sim.seek(final_time)

        # Position should match
        replayed_pos = sim.get_entity_position(entity_id)

        assert final_pos is not None
        assert replayed_pos is not None

        assert abs(final_pos[0] - replayed_pos[0]) < 0.1
        assert abs(final_pos[1] - replayed_pos[1]) < 0.1
        assert abs(final_pos[2] - replayed_pos[2]) < 0.1

    async def test_multiple_entities_replay_deterministically(self, sim):
        """Multiple entities with different movements replay correctly."""
        await sim.start()

        # Create entities with different velocities
        entity_ids = []
        velocities = [
            (10.0, 0.0, 0.0),
            (0.0, 15.0, 0.0),
            (5.0, 5.0, 0.0),
            (-10.0, 0.0, 0.0),
            (0.0, 0.0, 20.0),
        ]

        for i, velocity in enumerate(velocities):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i * 10), 0.0, 0.0),
            )
            entity_ids.append(entity_id)
            await sim.set_entity_velocity(entity_id, velocity=velocity)

        # Run simulation
        await asyncio.sleep(0.5)

        # Record positions
        target_time = sim.clock.get_time()
        original_positions = {}
        for entity_id in entity_ids:
            original_positions[entity_id] = sim.get_entity_position(entity_id)

        # Continue and rewind
        await asyncio.sleep(0.3)
        await sim.seek(target_time)

        # Check all positions match
        for entity_id in entity_ids:
            original = original_positions[entity_id]
            replayed = sim.get_entity_position(entity_id)

            assert original is not None
            assert replayed is not None

            # Within tolerance
            for i in range(3):
                assert abs(original[i] - replayed[i]) < 0.1


@pytest.mark.asyncio
class TestTimeTravel:
    """Test movement with time travel (rewind/fast-forward)."""

    async def test_rewind_moves_entity_backward(self, sim):
        """Rewinding shows entity at earlier position."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Move forward
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.5)

        # Record early position
        early_time = sim.clock.get_time()
        early_pos = sim.get_entity_position(entity_id)

        # Continue moving
        await asyncio.sleep(0.5)
        later_pos = sim.get_entity_position(entity_id)

        # Entity should have moved further
        assert later_pos is not None
        assert early_pos is not None
        assert later_pos[0] > early_pos[0]

        # Rewind
        await sim.seek(early_time)

        # Position should match early position
        rewound_pos = sim.get_entity_position(entity_id)
        assert rewound_pos is not None
        assert abs(rewound_pos[0] - early_pos[0]) < 0.1

    async def test_entity_velocity_restored_on_rewind(self, sim):
        """Entity velocity is restored correctly on rewind."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set initial velocity
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.3)

        checkpoint_time = sim.clock.get_time()

        # Change velocity
        await sim.set_entity_velocity(entity_id, velocity=(20.0, 0.0, 0.0))
        await asyncio.sleep(0.3)

        # Rewind to before velocity change
        await sim.seek(checkpoint_time)

        # Velocity should be restored to 10 m/s
        entity = sim.get_entity(entity_id)
        assert entity is not None
        assert entity["velocity"] == (10.0, 0.0, 0.0)

    async def test_stopped_entity_remains_stopped_on_replay(self, sim):
        """Entity with zero velocity doesn't move on replay."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(100.0, 200.0, 0.0),
        )

        # Don't set velocity - entity should remain stationary
        await asyncio.sleep(0.5)

        pos1 = sim.get_entity_position(entity_id)

        # Rewind to start
        await sim.seek(0.0)

        # Position should be original position
        pos2 = sim.get_entity_position(entity_id)

        assert pos1 == (100.0, 200.0, 0.0)
        assert pos2 == (100.0, 200.0, 0.0)


@pytest.mark.asyncio
class TestCheckpointCompatibility:
    """Test movement works with checkpoint/restore."""

    async def test_moving_entity_survives_checkpoint_restore(self, sim):
        """Moving entity state restored from checkpoint."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        await sim.set_entity_velocity(entity_id, velocity=(10.0, 5.0, 0.0))

        # Run long enough to create checkpoint
        await asyncio.sleep(1.5)

        checkpoint_time = sim.clock.get_time()
        checkpoint_pos = sim.get_entity_position(entity_id)

        # Continue simulation
        await asyncio.sleep(0.5)

        # Seek back to checkpoint time
        await sim.seek(checkpoint_time)

        # Position and velocity should be restored
        restored_pos = sim.get_entity_position(entity_id)
        entity = sim.get_entity(entity_id)

        assert entity is not None
        assert entity["velocity"] == (10.0, 5.0, 0.0)

        assert checkpoint_pos is not None
        assert restored_pos is not None
        assert abs(checkpoint_pos[0] - restored_pos[0]) < 0.1
        assert abs(checkpoint_pos[1] - restored_pos[1]) < 0.1

    async def test_entity_positions_consistent_across_rewind(self, sim):
        """Entity positions remain consistent through multiple rewinds."""
        await sim.start()

        # Create entities
        entity_ids = []
        for i in range(10):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i * 10), 0.0, 0.0),
            )
            await sim.set_entity_velocity(entity_id, velocity=(5.0, 0.0, 0.0))
            entity_ids.append(entity_id)

        # Run simulation
        await asyncio.sleep(1.0)

        target_time = sim.clock.get_time()

        # Record positions multiple times by rewinding
        positions_1 = {}
        for entity_id in entity_ids:
            positions_1[entity_id] = sim.get_entity_position(entity_id)

        # Continue and rewind again
        await asyncio.sleep(0.5)
        await sim.seek(target_time)

        positions_2 = {}
        for entity_id in entity_ids:
            positions_2[entity_id] = sim.get_entity_position(entity_id)

        # Rewind one more time
        await asyncio.sleep(0.5)
        await sim.seek(target_time)

        positions_3 = {}
        for entity_id in entity_ids:
            positions_3[entity_id] = sim.get_entity_position(entity_id)

        # All three measurements should be identical
        for entity_id in entity_ids:
            pos1 = positions_1[entity_id]
            pos2 = positions_2[entity_id]
            pos3 = positions_3[entity_id]

            assert pos1 is not None
            assert pos2 is not None
            assert pos3 is not None

            for i in range(3):
                assert abs(pos1[i] - pos2[i]) < 0.01
                assert abs(pos1[i] - pos3[i]) < 0.01
                assert abs(pos2[i] - pos3[i]) < 0.01


@pytest.mark.asyncio
class TestInterpolationAccuracy:
    """Test position interpolation accuracy."""

    async def test_interpolation_matches_expected_distance(self, sim):
        """Interpolated position matches velocity * time formula."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        velocity = (10.0, 5.0, 2.0)
        await sim.set_entity_velocity(entity_id, velocity=velocity)

        # Wait exactly 1 second
        await asyncio.sleep(1.0)

        pos = sim.get_entity_position(entity_id)
        assert pos is not None

        # Position should be velocity * time (allowing 10% tolerance)
        assert 9.0 < pos[0] < 11.0  # Expected 10
        assert 4.5 < pos[1] < 5.5   # Expected 5
        assert 1.8 < pos[2] < 2.2   # Expected 2

    async def test_interpolation_after_velocity_change(self, sim):
        """Interpolation correct after changing velocity mid-flight."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Move at 10 m/s for 1 second -> should be at x=10
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(1.0)

        pos_before_change = sim.get_entity_position(entity_id)

        # Change to 5 m/s and move for 1 more second -> x should increase by 5
        await sim.set_entity_velocity(entity_id, velocity=(5.0, 0.0, 0.0))
        await asyncio.sleep(1.0)

        pos_after_change = sim.get_entity_position(entity_id)

        assert pos_before_change is not None
        assert pos_after_change is not None

        # First segment: 0 + 10*1 = 10
        assert 9.0 < pos_before_change[0] < 11.0

        # Second segment: 10 + 5*1 = 15
        assert 14.0 < pos_after_change[0] < 16.0
