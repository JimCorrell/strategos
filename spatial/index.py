# spatial/index.py

"""Spatial indexing using R-tree for efficient proximity queries."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

import rtree.index

from core.events import Event, EventType
from core.logging import get_logger

if TYPE_CHECKING:
    from core.simulation import Simulation

from .entities import Position, get_interpolated_position

logger = get_logger(__name__)


class SpatialIndex:
    """R-tree based spatial index for entity positions.

    Provides efficient spatial queries (radius, bounding box, nearest neighbors)
    for entities in the simulation. Updates automatically via event handlers.
    """

    def __init__(self):
        """Initialize spatial index with R-tree backend."""
        self.simulation: Optional["Simulation"] = None

        # Create R-tree index with 3D coordinates
        # Properties: dimension=3 for (x, y, z)
        properties = rtree.index.Property()
        properties.dimension = 3
        self._rtree = rtree.index.Index(properties=properties)

        # Track entity positions for updates
        self._entity_positions: dict[UUID, Position] = {}

        self.logger = get_logger(f"{__name__}.SpatialIndex")
        self.logger.info("spatial_index.created")

    async def initialize(self, simulation: "Simulation") -> None:
        """Initialize and register event handlers.

        Args:
            simulation: Simulation instance to attach to
        """
        self.simulation = simulation

        # Register event handlers
        self.simulation.on_event(EventType.ENTITY_CREATED, self._handle_entity_created)
        self.simulation.on_event(EventType.ENTITY_MOVED, self._handle_entity_moved)
        self.simulation.on_event(EventType.ENTITY_DESTROYED, self._handle_entity_destroyed)

        self.logger.info("spatial_index.initialized")

    def insert(self, entity_id: UUID, position: Position) -> None:
        """Insert entity into spatial index.

        Args:
            entity_id: Entity UUID
            position: (x, y, z) position
        """
        # Create bounding box (point with no extent)
        bbox = (position[0], position[1], position[2],
                position[0], position[1], position[2])

        # Insert with entity_id hash as integer key (rtree requires int)
        self._rtree.insert(id(entity_id), bbox, obj=entity_id)
        self._entity_positions[entity_id] = position

        self.logger.debug(
            "entity.indexed",
            entity_id=str(entity_id),
            position=position,
        )

    def update(self, entity_id: UUID, new_position: Position) -> None:
        """Update entity position in spatial index.

        Args:
            entity_id: Entity UUID
            new_position: New (x, y, z) position
        """
        if entity_id not in self._entity_positions:
            # Entity not in index, insert it
            self.insert(entity_id, new_position)
            return

        old_position = self._entity_positions[entity_id]

        # Create old bounding box for deletion
        old_bbox = (old_position[0], old_position[1], old_position[2],
                    old_position[0], old_position[1], old_position[2])

        # Create new bounding box for insertion
        new_bbox = (new_position[0], new_position[1], new_position[2],
                    new_position[0], new_position[1], new_position[2])

        # Delete old entry and insert new one
        self._rtree.delete(id(entity_id), old_bbox)
        self._rtree.insert(id(entity_id), new_bbox, obj=entity_id)

        self._entity_positions[entity_id] = new_position

    def remove(self, entity_id: UUID) -> None:
        """Remove entity from spatial index.

        Args:
            entity_id: Entity UUID
        """
        if entity_id not in self._entity_positions:
            return

        position = self._entity_positions[entity_id]
        bbox = (position[0], position[1], position[2],
                position[0], position[1], position[2])

        self._rtree.delete(id(entity_id), bbox)
        del self._entity_positions[entity_id]

        self.logger.debug("entity.removed_from_index", entity_id=str(entity_id))

    def query_radius(
        self,
        center: Position,
        radius: float,
        include_z: bool = False,
    ) -> list[UUID]:
        """Find entities within radius of center point.

        Args:
            center: Center position (x, y, z)
            radius: Search radius
            include_z: If True, use 3D distance; if False, use 2D (x, y only)

        Returns:
            List of entity UUIDs within radius
        """
        # Create search bounding box
        # For 2D queries (include_z=False), use full Z range
        if include_z:
            bbox = (
                center[0] - radius,
                center[1] - radius,
                center[2] - radius,
                center[0] + radius,
                center[1] + radius,
                center[2] + radius,
            )
        else:
            # 2D query: use very large Z range to include all entities
            bbox = (
                center[0] - radius,
                center[1] - radius,
                -1e10,  # Very large negative Z
                center[0] + radius,
                center[1] + radius,
                1e10,  # Very large positive Z
            )

        # Query R-tree for candidates
        candidates = list(self._rtree.intersection(bbox, objects=True))

        # Filter by actual distance
        results = []
        for item in candidates:
            entity_id = item.object
            entity_pos = self._entity_positions.get(entity_id)
            if entity_pos:
                if include_z:
                    # 3D distance
                    dx = entity_pos[0] - center[0]
                    dy = entity_pos[1] - center[1]
                    dz = entity_pos[2] - center[2]
                    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                else:
                    # 2D distance (ignore z)
                    dx = entity_pos[0] - center[0]
                    dy = entity_pos[1] - center[1]
                    dist = (dx * dx + dy * dy) ** 0.5

                if dist <= radius:
                    results.append(entity_id)

        return results

    def query_bbox(
        self,
        min_point: Position,
        max_point: Position,
    ) -> list[UUID]:
        """Find entities within bounding box.

        Args:
            min_point: Minimum corner (x, y, z)
            max_point: Maximum corner (x, y, z)

        Returns:
            List of entity UUIDs within bounding box
        """
        bbox = (
            min_point[0], min_point[1], min_point[2],
            max_point[0], max_point[1], max_point[2],
        )

        candidates = list(self._rtree.intersection(bbox, objects=True))
        return [item.object for item in candidates]

    def nearest_neighbors(
        self,
        point: Position,
        k: int = 1,
        include_z: bool = False,
    ) -> list[tuple[UUID, float]]:
        """Find k nearest entities to a point.

        Args:
            point: Query point (x, y, z)
            k: Number of nearest neighbors to find
            include_z: If True, use 3D distance; if False, use 2D

        Returns:
            List of (entity_id, distance) tuples, sorted by distance
        """
        # Create point bbox for query
        bbox = (point[0], point[1], point[2], point[0], point[1], point[2])

        # Query k nearest
        candidates = list(self._rtree.nearest(bbox, k, objects=True))

        # Calculate actual distances
        results = []
        for item in candidates:
            entity_id = item.object
            entity_pos = self._entity_positions.get(entity_id)
            if entity_pos:
                if include_z:
                    dx = entity_pos[0] - point[0]
                    dy = entity_pos[1] - point[1]
                    dz = entity_pos[2] - point[2]
                    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                else:
                    dx = entity_pos[0] - point[0]
                    dy = entity_pos[1] - point[1]
                    dist = (dx * dx + dy * dy) ** 0.5

                results.append((entity_id, dist))

        # Sort by distance
        results.sort(key=lambda x: x[1])
        return results

    def get_entity_count(self) -> int:
        """Get total number of entities in index.

        Returns:
            Number of indexed entities
        """
        return len(self._entity_positions)

    def clear(self) -> None:
        """Clear all entities from index."""
        # Rebuild R-tree from scratch
        properties = rtree.index.Property()
        properties.dimension = 3
        self._rtree = rtree.index.Index(properties=properties)
        self._entity_positions.clear()

        self.logger.info("spatial_index.cleared")

    # Event Handlers

    async def _handle_entity_created(self, event: Event) -> None:
        """Handle ENTITY_CREATED event."""
        entity_id = UUID(event.data["entity_id"])
        position = tuple(event.data["position"])
        self.insert(entity_id, position)

    async def _handle_entity_moved(self, event: Event) -> None:
        """Handle ENTITY_MOVED event."""
        entity_id = UUID(event.data["entity_id"])

        # Get current position with interpolation if entity has velocity
        if self.simulation:
            entity = self.simulation.state.entities.get(entity_id)
            if entity:
                velocity = entity.get("velocity", (0, 0, 0))
                last_update = entity.get("last_update_time", 0.0)
                current_time = self.simulation.clock.get_time()

                # Calculate interpolated position
                position = get_interpolated_position(
                    tuple(entity["position"]),
                    velocity,
                    last_update,
                    current_time,
                )
                self.update(entity_id, position)
        else:
            # Fallback: use position from event
            position = tuple(event.data["position"])
            self.update(entity_id, position)

    async def _handle_entity_destroyed(self, event: Event) -> None:
        """Handle ENTITY_DESTROYED event."""
        entity_id = UUID(event.data["entity_id"])
        self.remove(entity_id)
