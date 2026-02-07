# tests/test_phase2_entities.py

"""Tests for Phase 2a entity creation and destruction."""

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
class TestEntityCreation:
    """Test entity creation functionality."""

    async def test_create_entity_basic(self, sim):
        """Can create a basic entity."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(100.0, 200.0, 0.0),
        )

        assert isinstance(entity_id, UUID)
        assert entity_id in sim.state.entities

        entity = sim.get_entity(entity_id)
        assert entity is not None
        assert entity["type"] == "infantry"
        assert entity["position"] == (100.0, 200.0, 0.0)
        assert entity["max_speed"] == 10.0  # Default

    async def test_create_entity_with_metadata(self, sim):
        """Can create entity with metadata."""
        await sim.start()

        metadata = {"squad": "alpha", "rank": "sergeant"}

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
            max_speed=15.0,
            metadata=metadata,
        )

        entity = sim.get_entity(entity_id)
        assert entity["metadata"] == metadata
        assert entity["max_speed"] == 15.0

    async def test_create_entity_2d_position(self, sim):
        """Can create entity with 2D position (auto-adds z=0)."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="tank",
            position=(50.0, 75.0),  # 2D position
        )

        entity = sim.get_entity(entity_id)
        # Should be converted to 3D with z=0
        assert len(entity["position"]) == 3
        assert entity["position"][2] == 0.0

    async def test_create_multiple_entities(self, sim):
        """Can create multiple entities."""
        await sim.start()

        entity_ids = []
        for i in range(10):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i * 10), 0.0, 0.0),
            )
            entity_ids.append(entity_id)

        assert len(sim.state.entities) == 10

        # All entities should be queryable
        for entity_id in entity_ids:
            entity = sim.get_entity(entity_id)
            assert entity is not None

    async def test_create_entities_by_type_tracking(self, sim):
        """Entities are tracked by type."""
        await sim.start()

        # Create mixed entity types
        infantry_ids = []
        for i in range(5):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i), 0.0, 0.0),
            )
            infantry_ids.append(entity_id)

        tank_ids = []
        for i in range(3):
            entity_id = await sim.create_entity(
                entity_type="tank",
                position=(float(i), 100.0, 0.0),
            )
            tank_ids.append(entity_id)

        # Query by type
        infantry_result = sim.get_entities_by_type("infantry")
        tank_result = sim.get_entities_by_type("tank")

        assert len(infantry_result) == 5
        assert len(tank_result) == 3

        for entity_id in infantry_ids:
            assert entity_id in infantry_result

        for entity_id in tank_ids:
            assert entity_id in tank_result


@pytest.mark.asyncio
class TestEntityDestruction:
    """Test entity destruction functionality."""

    async def test_destroy_entity(self, sim):
        """Can destroy an entity."""
        await sim.start()

        # Create entity
        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(100.0, 200.0, 0.0),
        )

        assert entity_id in sim.state.entities

        # Destroy entity
        await sim.destroy_entity(entity_id)

        # Entity should be removed
        assert entity_id not in sim.state.entities
        entity = sim.get_entity(entity_id)
        assert entity is None

    async def test_destroy_removes_from_type_tracking(self, sim):
        """Destroying entity removes it from type tracking."""
        await sim.start()

        entity_id = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        infantry_entities = sim.get_entities_by_type("infantry")
        assert entity_id in infantry_entities

        # Destroy entity
        await sim.destroy_entity(entity_id)

        # Should be removed from type tracking
        infantry_entities = sim.get_entities_by_type("infantry")
        assert entity_id not in infantry_entities


@pytest.mark.asyncio
class TestEntityQueries:
    """Test entity query functionality."""

    async def test_query_entities_in_radius(self, sim):
        """Can query entities within radius."""
        await sim.start()

        # Create entities in a grid
        for x in range(5):
            for y in range(5):
                await sim.create_entity(
                    entity_type="infantry",
                    position=(float(x * 100), float(y * 100), 0.0),
                )

        # Give events time to process
        await asyncio.sleep(0.1)

        # Query center area (should find entities near (200, 200))
        center = (200.0, 200.0, 0.0)
        radius = 150.0

        results = sim.query_entities_in_radius(center, radius)

        # Should find some entities (exact count depends on distance calculation)
        assert len(results) > 0
        assert len(results) <= 25  # Can't be more than total

    async def test_query_empty_radius(self, sim):
        """Query in empty area returns no results."""
        await sim.start()

        # Create entities far away
        await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        await asyncio.sleep(0.1)

        # Query far from entities
        center = (1000.0, 1000.0, 0.0)
        radius = 10.0

        results = sim.query_entities_in_radius(center, radius)
        assert len(results) == 0


@pytest.mark.asyncio
class TestEntityCheckpoints:
    """Test entities survive checkpoint/restore cycle."""

    async def test_entities_survive_checkpoint(self, sim):
        """Entities persist through checkpoint restore."""
        await sim.start()

        # Create entities
        entity_ids = []
        for i in range(5):
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(float(i * 10), 0.0, 0.0),
            )
            entity_ids.append(entity_id)

        # Let simulation run to create checkpoint
        await asyncio.sleep(0.5)

        current_time = sim.clock.get_time()

        # Seek to time (will restore from checkpoint)
        await sim.seek(current_time)

        # Entities should still exist
        assert len(sim.state.entities) == 5

        for entity_id in entity_ids:
            entity = sim.get_entity(entity_id)
            assert entity is not None

    async def test_entities_removed_on_rewind(self, sim):
        """Entities created after rewind point are removed."""
        await sim.start()

        # Wait a bit for simulation to stabilize
        await asyncio.sleep(0.1)

        # Create entity at early time
        early_entity = await sim.create_entity(
            entity_type="infantry",
            position=(0.0, 0.0, 0.0),
        )

        await asyncio.sleep(0.3)
        early_time = sim.clock.get_time()

        # Create entity at later time
        await asyncio.sleep(0.3)
        late_entity = await sim.create_entity(
            entity_type="infantry",
            position=(100.0, 0.0, 0.0),
        )

        await asyncio.sleep(0.1)

        assert len(sim.state.entities) == 2

        # Rewind to time between the two creations (slightly after early_time)
        await sim.seek(early_time + 0.1)

        # Only early entity should exist (late entity created after seek point)
        assert early_entity in sim.state.entities
        assert late_entity not in sim.state.entities


@pytest.mark.asyncio
class TestPhase2aSuccessCriteria:
    """Test Phase 2a success criteria."""

    async def test_1000_entities_created(self, sim):
        """Can create 1000 entities successfully."""
        await sim.start()

        entity_ids = []
        for i in range(1000):
            x = (i % 50) * 20.0
            y = (i // 50) * 20.0

            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(x, y, 0.0),
            )
            entity_ids.append(entity_id)

        # All entities should be created
        assert len(sim.state.entities) == 1000

        # All should be queryable
        for entity_id in entity_ids:
            entity = sim.get_entity(entity_id)
            assert entity is not None

    async def test_radius_query_performance(self, sim):
        """Radius queries complete in <10ms with 1000 entities."""
        await sim.start()

        # Create 1000 entities
        for i in range(1000):
            x = (i % 50) * 20.0
            y = (i // 50) * 20.0

            await sim.create_entity(
                entity_type="infantry",
                position=(x, y, 0.0),
            )

        # Give spatial index time to update
        await asyncio.sleep(0.2)

        import time

        # Run multiple queries and measure time
        query_times = []
        for _ in range(10):
            center = (500.0, 500.0, 0.0)
            radius = 50.0

            start = time.perf_counter()
            results = sim.query_entities_in_radius(center, radius)
            duration = time.perf_counter() - start

            query_times.append(duration)

        avg_time = sum(query_times) / len(query_times)

        # Average should be under 10ms
        assert avg_time < 0.010, f"Average query time {avg_time}s exceeds 10ms"

    async def test_entities_survive_checkpoint_restore(self, sim):
        """1000 entities survive checkpoint/restore cycle."""
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

        # Let simulation run
        await asyncio.sleep(0.5)
        checkpoint_time = sim.clock.get_time()

        # Seek to current time (will restore from checkpoint)
        await sim.seek(checkpoint_time)

        # All entities should still exist
        assert len(sim.state.entities) == 1000

        # Random sample should be queryable
        import random
        sample_ids = random.sample(entity_ids, 10)

        for entity_id in sample_ids:
            entity = sim.get_entity(entity_id)
            assert entity is not None
