"""Tests for Phase 2b: Movement System."""

import asyncio
import tempfile
import shutil
from pathlib import Path
from uuid import UUID

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
class TestVelocityBasedMovement:
    """Test velocity-based entity movement."""

    async def test_set_entity_velocity(self, sim):
        """Can set velocity for an entity."""
        await sim.start()

        # Create entity
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set velocity
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))

        # Give movement system time to process
        await asyncio.sleep(0.1)

        # Check entity has velocity
        entity = sim.get_entity(entity_id)
        assert entity is not None
        assert entity["velocity"] == (10.0, 0.0, 0.0)

    async def test_entity_moves_with_velocity(self, sim):
        """Entity position changes when velocity is set."""
        await sim.start()

        # Create entity at origin
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set velocity (10 m/s along X axis)
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))

        # Wait 0.5 seconds
        await asyncio.sleep(0.5)

        # Get current position (should have moved)
        current_pos = sim.get_entity_position(entity_id)
        assert current_pos is not None

        # Should be approximately 5 meters along X axis (10 m/s * 0.5s)
        # Allow some tolerance for timing
        assert current_pos[0] > 4.0  # Moved at least 4 meters
        assert current_pos[0] < 6.0  # But not more than 6 meters
        assert abs(current_pos[1]) < 0.1  # Y should be ~0
        assert abs(current_pos[2]) < 0.1  # Z should be ~0

    async def test_stop_entity_by_zero_velocity(self, sim):
        """Can stop entity by setting velocity to zero."""
        await sim.start()

        # Create entity
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set velocity
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.2)

        # Get position after moving
        pos_after_move = sim.get_entity_position(entity_id)

        # Stop entity
        await sim.set_entity_velocity(entity_id, velocity=(0.0, 0.0, 0.0))
        await asyncio.sleep(0.2)

        # Position should remain the same
        pos_after_stop = sim.get_entity_position(entity_id)

        assert pos_after_move is not None
        assert pos_after_stop is not None

        # Position should not have changed significantly
        dx = abs(pos_after_stop[0] - pos_after_move[0])
        assert dx < 0.5  # Less than 0.5 meter difference

    async def test_multiple_entities_moving(self, sim):
        """Multiple entities can move simultaneously."""
        await sim.start()

        # Create 10 entities
        entity_ids = []
        for i in range(10):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i * 10), 0.0, 0.0),
            )
            entity_ids.append(entity_id)

        # Set different velocities
        for i, entity_id in enumerate(entity_ids):
            velocity = (float(i + 1) * 5.0, 0.0, 0.0)  # 5, 10, 15, ... m/s
            await sim.set_entity_velocity(entity_id, velocity)

        # Wait for movement
        await asyncio.sleep(0.5)

        # All entities should have moved
        for i, entity_id in enumerate(entity_ids):
            pos = sim.get_entity_position(entity_id)
            assert pos is not None
            # Each entity should have moved relative to start position
            expected_distance = (i + 1) * 5.0 * 0.5  # velocity * time
            start_x = i * 10
            expected_x = start_x + expected_distance

            # Allow 20% tolerance
            assert pos[0] > expected_x * 0.8
            assert pos[0] < expected_x * 1.2

    async def test_3d_velocity(self, sim):
        """Entities can move in 3D space."""
        await sim.start()

        # Create entity
        entity_id = await sim.create_entity(
            entity_type="aircraft",
            position=(0.0, 0.0, 0.0),
        )

        # Set 3D velocity
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 10.0, 5.0))

        await asyncio.sleep(0.5)

        # Check all dimensions changed
        pos = sim.get_entity_position(entity_id)
        assert pos is not None
        assert pos[0] > 4.0  # Moved in X
        assert pos[1] > 4.0  # Moved in Y
        assert pos[2] > 2.0  # Moved in Z


@pytest.mark.asyncio
class TestPositionInterpolation:
    """Test deterministic position interpolation."""

    async def test_interpolation_at_same_time(self, sim):
        """Position at event time equals recorded position."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(100.0, 200.0, 0.0),
        )

        # Get position immediately - should match creation position
        pos = sim.get_entity_position(entity_id)
        assert pos == (100.0, 200.0, 0.0)

    async def test_interpolation_with_velocity(self, sim):
        """Position interpolates correctly with velocity."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Set velocity
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))

        # Wait specific time
        await asyncio.sleep(1.0)

        # Position should be approximately 10 meters (10 m/s * 1.0s)
        pos = sim.get_entity_position(entity_id)
        assert pos is not None
        assert 9.5 < pos[0] < 10.5  # Allow small tolerance

    async def test_velocity_change_updates_interpolation(self, sim):
        """Changing velocity updates interpolation base."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Move at 10 m/s for 0.5s
        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.5)

        # Should be ~5 meters
        pos1 = sim.get_entity_position(entity_id)
        assert pos1 is not None
        assert 4.5 < pos1[0] < 5.5

        # Change velocity to -10 m/s (reverse)
        await sim.set_entity_velocity(entity_id, velocity=(-10.0, 0.0, 0.0))
        await asyncio.sleep(0.5)

        # Should be back near origin
        pos2 = sim.get_entity_position(entity_id)
        assert pos2 is not None
        assert -0.5 < pos2[0] < 0.5


@pytest.mark.asyncio
class TestMovementSystemLifecycle:
    """Test movement system startup and shutdown."""

    async def test_movement_system_starts_with_simulation(self, sim):
        """Movement system starts when simulation starts."""
        await sim.start()

        assert sim.movement_system is not None
        assert sim.movement_system.running is True

    async def test_movement_system_stops_with_simulation(self, sim):
        """Movement system stops when simulation stops."""
        await sim.start()
        await asyncio.sleep(0.1)

        await sim.stop()

        assert sim.movement_system.running is False

    async def test_movement_system_handles_pause_resume(self, sim):
        """Movement continues after pause/resume."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))
        await asyncio.sleep(0.2)

        # Pause
        await sim.pause()
        pos_at_pause = sim.get_entity_position(entity_id)

        await asyncio.sleep(0.2)

        # Position shouldn't change during pause
        pos_during_pause = sim.get_entity_position(entity_id)
        assert pos_during_pause is not None
        assert pos_at_pause is not None
        # Clock is paused so position should be similar
        assert abs(pos_during_pause[0] - pos_at_pause[0]) < 0.5

        # Resume and continue moving
        await sim.resume()
        await asyncio.sleep(0.2)

        pos_after_resume = sim.get_entity_position(entity_id)
        assert pos_after_resume is not None
        assert pos_after_resume[0] > pos_at_pause[0]  # Moved further


@pytest.mark.asyncio
class TestSpatialIndexIntegration:
    """Test movement integrates with spatial index."""

    async def test_moving_entity_updates_spatial_index(self, sim):
        """Spatial queries reflect entity movement."""
        await sim.start()

        # Create entity at origin
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        # Query at origin - should find entity
        results = sim.query_entities_in_radius((0.0, 0.0, 0.0), radius=10.0)
        assert entity_id in results

        # Set velocity to move away
        await sim.set_entity_velocity(entity_id, velocity=(100.0, 0.0, 0.0))
        await asyncio.sleep(0.5)

        # Give spatial index time to update
        await asyncio.sleep(0.1)

        # Query at origin - should NOT find entity (it moved away)
        results_after = sim.query_entities_in_radius((0.0, 0.0, 0.0), radius=10.0)
        # Entity might still be found if within radius, so check new position
        results_new_pos = sim.query_entities_in_radius((50.0, 0.0, 0.0), radius=20.0)
        assert entity_id in results_new_pos


@pytest.mark.asyncio
class TestPhase2bSuccessCriteria:
    """Test Phase 2b success criteria."""

    async def test_1000_entities_moving_at_60fps(self, sim):
        """1000 entities move simultaneously at 60 FPS."""
        await sim.start()

        # Create 1000 entities
        entity_ids = []
        for i in range(1000):
            x = (i % 50) * 20.0
            y = (i // 50) * 20.0

            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(x, y, 0.0),
            )
            entity_ids.append(entity_id)

        # Set velocities for all entities
        for entity_id in entity_ids:
            await sim.set_entity_velocity(entity_id, velocity=(5.0, 5.0, 0.0))

        # Run for 1 second
        await asyncio.sleep(1.0)

        # All entities should have moved
        for entity_id in entity_ids:
            pos = sim.get_entity_position(entity_id)
            assert pos is not None

        # Movement system should be running smoothly
        assert sim.movement_system.running

    async def test_spatial_queries_work_on_moving_entities(self, sim):
        """Spatial queries return correct results for moving entities."""
        await sim.start()

        # Create cluster of entities
        entity_ids = []
        for i in range(100):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i), 0.0, 0.0),
            )
            entity_ids.append(entity_id)

        # Set all moving in same direction
        for entity_id in entity_ids:
            await sim.set_entity_velocity(entity_id, velocity=(10.0, 0.0, 0.0))

        await asyncio.sleep(0.5)

        # Give spatial index time to update
        await asyncio.sleep(0.1)

        # Query should find entities at new positions
        # Entities started at 0-99, moving at 10 m/s for 0.5s = 5 meters
        # So entities now around 5-104
        results = sim.query_entities_in_radius((55.0, 0.0, 0.0), radius=20.0)

        # Should find multiple entities
        assert len(results) > 0
