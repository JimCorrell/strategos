# tests/test_spatial_index.py

"""Tests for spatial indexing system."""

import asyncio
import time
from uuid import uuid4

import pytest

from spatial import SpatialIndex
from spatial.entities import Position


class TestSpatialIndexBasics:
    """Test basic spatial index operations."""

    def test_create_spatial_index(self):
        """Can create spatial index."""
        index = SpatialIndex()
        assert index is not None
        assert index.get_entity_count() == 0

    def test_insert_entity(self):
        """Can insert entity into index."""
        index = SpatialIndex()
        entity_id = uuid4()
        position: Position = (100.0, 200.0, 0.0)

        index.insert(entity_id, position)

        assert index.get_entity_count() == 1
        assert entity_id in index._entity_positions
        assert index._entity_positions[entity_id] == position

    def test_insert_multiple_entities(self):
        """Can insert multiple entities."""
        index = SpatialIndex()
        entities = [
            (uuid4(), (float(i * 10), float(i * 10), 0.0))
            for i in range(10)
        ]

        for entity_id, position in entities:
            index.insert(entity_id, position)

        assert index.get_entity_count() == 10

    def test_remove_entity(self):
        """Can remove entity from index."""
        index = SpatialIndex()
        entity_id = uuid4()
        position: Position = (100.0, 200.0, 0.0)

        index.insert(entity_id, position)
        assert index.get_entity_count() == 1

        index.remove(entity_id)
        assert index.get_entity_count() == 0
        assert entity_id not in index._entity_positions

    def test_remove_nonexistent_entity(self):
        """Removing nonexistent entity doesn't raise error."""
        index = SpatialIndex()
        entity_id = uuid4()

        # Should not raise
        index.remove(entity_id)
        assert index.get_entity_count() == 0

    def test_update_entity_position(self):
        """Can update entity position."""
        index = SpatialIndex()
        entity_id = uuid4()
        old_position: Position = (100.0, 200.0, 0.0)
        new_position: Position = (150.0, 250.0, 0.0)

        index.insert(entity_id, old_position)
        index.update(entity_id, new_position)

        assert index.get_entity_count() == 1
        assert index._entity_positions[entity_id] == new_position

    def test_clear_index(self):
        """Can clear all entities from index."""
        index = SpatialIndex()

        # Add 10 entities
        for i in range(10):
            index.insert(uuid4(), (float(i * 10), float(i * 10), 0.0))

        assert index.get_entity_count() == 10

        index.clear()
        assert index.get_entity_count() == 0


class TestSpatialQueries:
    """Test spatial query operations."""

    def test_query_radius_empty(self):
        """Query on empty index returns empty list."""
        index = SpatialIndex()
        results = index.query_radius((0.0, 0.0, 0.0), radius=50.0)
        assert results == []

    def test_query_radius_2d(self):
        """Can query entities within 2D radius."""
        index = SpatialIndex()

        # Place entities in a grid
        entities = {}
        for x in range(5):
            for y in range(5):
                entity_id = uuid4()
                position: Position = (float(x * 10), float(y * 10), 0.0)
                entities[entity_id] = position
                index.insert(entity_id, position)

        # Query center with radius 15
        center: Position = (20.0, 20.0, 0.0)
        results = index.query_radius(center, radius=15.0)

        # Should find at least the center entity and nearby ones
        assert len(results) >= 1  # At least center entity
        assert len(results) <= 25  # At most all entities in grid

    def test_query_radius_3d(self):
        """Can query entities with 3D distance."""
        index = SpatialIndex()

        # Place entities at different heights
        ground_entity = uuid4()
        index.insert(ground_entity, (0.0, 0.0, 0.0))

        air_entity = uuid4()
        index.insert(air_entity, (0.0, 0.0, 100.0))

        # 2D query (ignore Z) should find both (they're at same x,y)
        results_2d = index.query_radius((0.0, 0.0, 50.0), radius=10.0, include_z=False)
        assert ground_entity in results_2d
        assert air_entity in results_2d

        # 3D query from ground level should only find ground entity
        results_3d = index.query_radius((0.0, 0.0, 0.0), radius=50.0, include_z=True)
        assert ground_entity in results_3d
        # Air entity is 100 units away in 3D, so shouldn't be found with radius 50
        assert air_entity not in results_3d

    def test_query_bbox(self):
        """Can query entities within bounding box."""
        index = SpatialIndex()

        # Place entities
        inside_entity = uuid4()
        index.insert(inside_entity, (50.0, 50.0, 0.0))

        outside_entity = uuid4()
        index.insert(outside_entity, (150.0, 150.0, 0.0))

        # Query bbox (0,0,0) to (100,100,10)
        results = index.query_bbox(
            (0.0, 0.0, 0.0),
            (100.0, 100.0, 10.0),
        )

        assert inside_entity in results
        assert outside_entity not in results

    def test_nearest_neighbors(self):
        """Can find k nearest neighbors."""
        index = SpatialIndex()

        # Place entities at known positions
        entities = [
            (uuid4(), (0.0, 0.0, 0.0)),  # Closest
            (uuid4(), (10.0, 0.0, 0.0)),  # Second closest
            (uuid4(), (20.0, 0.0, 0.0)),  # Third
            (uuid4(), (100.0, 0.0, 0.0)),  # Far away
        ]

        for entity_id, position in entities:
            index.insert(entity_id, position)

        # Find 2 nearest to origin
        query_point: Position = (0.0, 0.0, 0.0)
        results = index.nearest_neighbors(query_point, k=2)

        assert len(results) == 2
        # Should be sorted by distance
        assert results[0][1] <= results[1][1]

        # Closest should be at origin
        assert results[0][0] == entities[0][0]
        assert results[0][1] == 0.0

    def test_nearest_neighbors_3d(self):
        """Can find nearest neighbors with 3D distance."""
        index = SpatialIndex()

        ground_entity = uuid4()
        index.insert(ground_entity, (0.0, 0.0, 0.0))

        air_entity = uuid4()
        index.insert(air_entity, (0.0, 0.0, 50.0))

        far_entity = uuid4()
        index.insert(far_entity, (100.0, 0.0, 0.0))

        # Find nearest to origin with 3D distance
        query_point: Position = (0.0, 0.0, 0.0)
        results = index.nearest_neighbors(query_point, k=2, include_z=True)

        # Ground entity should be closest
        assert results[0][0] == ground_entity
        assert results[0][1] == 0.0


class TestSpatialIndexPerformance:
    """Test spatial index performance."""

    def test_insert_1000_entities_fast(self):
        """Can insert 1000 entities quickly."""
        index = SpatialIndex()

        start = time.perf_counter()

        for i in range(1000):
            entity_id = uuid4()
            position: Position = (float(i % 100), float(i // 100), 0.0)
            index.insert(entity_id, position)

        duration = time.perf_counter() - start

        assert index.get_entity_count() == 1000
        # Should complete in under 1 second
        assert duration < 1.0

    def test_query_radius_performance(self):
        """Radius queries complete in <10ms with 1000 entities."""
        index = SpatialIndex()

        # Create 1000 entities in a grid
        for i in range(1000):
            entity_id = uuid4()
            x = (i % 100) * 10.0
            y = (i // 100) * 10.0
            index.insert(entity_id, (x, y, 0.0))

        # Run 100 queries and measure average time
        query_times = []

        for _ in range(100):
            center: Position = (500.0, 500.0, 0.0)
            radius = 50.0

            start = time.perf_counter()
            results = index.query_radius(center, radius)
            duration = time.perf_counter() - start

            query_times.append(duration)

        avg_query_time = sum(query_times) / len(query_times)

        # Average query should be under 10ms
        assert avg_query_time < 0.010, f"Avg query time {avg_query_time}s exceeds 10ms"

    def test_update_1000_entities_fast(self):
        """Can update 1000 entities quickly."""
        index = SpatialIndex()

        # Insert 1000 entities
        entities = []
        for i in range(1000):
            entity_id = uuid4()
            position: Position = (float(i), 0.0, 0.0)
            index.insert(entity_id, position)
            entities.append(entity_id)

        # Update all positions
        start = time.perf_counter()

        for i, entity_id in enumerate(entities):
            new_position: Position = (float(i), 100.0, 0.0)
            index.update(entity_id, new_position)

        duration = time.perf_counter() - start

        # Should complete in under 2 seconds
        assert duration < 2.0


@pytest.mark.asyncio
class TestSpatialIndexIntegration:
    """Test spatial index integration with simulation."""

    async def test_initialize_with_simulation(self):
        """Can initialize spatial index with simulation."""
        from core.simulation import Simulation
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        db_path = str(temp_dir / "test.db")
        checkpoint_dir = str(temp_dir / "checkpoints")
        Path(checkpoint_dir).mkdir()

        try:
            sim = Simulation(db_path=db_path, checkpoint_dir=checkpoint_dir)
            await sim.initialize()

            assert sim.spatial_index is not None
            assert sim.spatial_index.simulation == sim

            await sim.shutdown()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_entity_created_event_updates_index(self):
        """ENTITY_CREATED event automatically updates spatial index."""
        from core.simulation import Simulation
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        db_path = str(temp_dir / "test.db")
        checkpoint_dir = str(temp_dir / "checkpoints")
        Path(checkpoint_dir).mkdir()

        try:
            sim = Simulation(db_path=db_path, checkpoint_dir=checkpoint_dir)
            await sim.initialize()
            await sim.start()

            # Create entity
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(100.0, 200.0, 0.0),
            )

            # Give event handlers time to process
            await asyncio.sleep(0.1)

            # Check spatial index was updated
            assert sim.spatial_index.get_entity_count() == 1
            assert entity_id in sim.spatial_index._entity_positions

            await sim.shutdown()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_entity_destroyed_event_updates_index(self):
        """ENTITY_DESTROYED event automatically updates spatial index."""
        from core.simulation import Simulation
        import tempfile
        import shutil
        from pathlib import Path

        temp_dir = Path(tempfile.mkdtemp())
        db_path = str(temp_dir / "test.db")
        checkpoint_dir = str(temp_dir / "checkpoints")
        Path(checkpoint_dir).mkdir()

        try:
            sim = Simulation(db_path=db_path, checkpoint_dir=checkpoint_dir)
            await sim.initialize()
            await sim.start()

            # Create entity
            entity_id = await sim.create_entity(
                entity_type="infantry",
                position=(100.0, 200.0, 0.0),
            )

            await asyncio.sleep(0.1)
            assert sim.spatial_index.get_entity_count() == 1

            # Destroy entity
            await sim.destroy_entity(entity_id)
            await asyncio.sleep(0.1)

            # Check spatial index was updated
            assert sim.spatial_index.get_entity_count() == 0
            assert entity_id not in sim.spatial_index._entity_positions

            await sim.shutdown()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
