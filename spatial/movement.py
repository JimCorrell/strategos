"""Movement system for entity motion simulation.

Handles velocity-based movement with smooth interpolation and 60Hz updates.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from core.events import EventType
from core.logging import get_logger
from spatial.entities import Position, get_interpolated_position

if TYPE_CHECKING:
    from core.simulation import Simulation

logger = get_logger(__name__)


class MovementSystem:
    """Manages entity movement with velocity-based interpolation.

    The movement system:
    - Runs at 60Hz to update entity positions
    - Uses velocity vectors for smooth movement
    - Interpolates positions deterministically for replay
    - Updates spatial index as entities move
    """

    def __init__(self, simulation: "Simulation"):
        """Initialize movement system.

        Args:
            simulation: Parent simulation instance
        """
        self.simulation = simulation
        self.running = False
        self.update_task: Optional[asyncio.Task] = None
        self.target_fps = 60
        self.frame_time = 1.0 / self.target_fps

        # Performance tracking
        self.frame_count = 0
        self.total_frame_time = 0.0
        self.last_stats_time = time.perf_counter()

    async def initialize(self) -> None:
        """Initialize the movement system."""
        logger.info("MovementSystem initialized", target_fps=self.target_fps)

    async def start(self) -> None:
        """Start the movement update loop."""
        if self.running:
            logger.warning("MovementSystem already running")
            return

        self.running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("MovementSystem started")

    async def stop(self) -> None:
        """Stop the movement update loop."""
        if not self.running:
            return

        self.running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
            self.update_task = None

        logger.info("MovementSystem stopped")

    async def _update_loop(self) -> None:
        """Main update loop running at target FPS."""
        try:
            while self.running:
                frame_start = time.perf_counter()

                # Update all moving entities
                await self._update_entities()

                # Calculate frame timing
                frame_duration = time.perf_counter() - frame_start
                self.frame_count += 1
                self.total_frame_time += frame_duration

                # Log performance stats periodically
                if time.perf_counter() - self.last_stats_time > 10.0:
                    self._log_performance_stats()

                # Sleep to maintain target FPS
                sleep_time = max(0, self.frame_time - frame_duration)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    # Frame took longer than target - log warning
                    if frame_duration > self.frame_time * 2:
                        logger.warning(
                            "Slow frame detected",
                            frame_duration_ms=frame_duration * 1000,
                            target_ms=self.frame_time * 1000,
                        )

        except asyncio.CancelledError:
            logger.debug("Movement update loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in movement update loop", error=str(e), exc_info=True)
            self.running = False

    async def _update_entities(self) -> None:
        """Update positions of all moving entities."""
        if not self.simulation.state:
            return

        current_time = self.simulation.clock.get_time()
        moving_entities = []

        # Find entities with non-zero velocity
        for entity_id, entity in self.simulation.state.entities.items():
            velocity = entity.get("velocity", (0.0, 0.0, 0.0))

            # Check if entity is moving
            if any(v != 0.0 for v in velocity):
                moving_entities.append((entity_id, entity))

        # Update positions based on interpolation
        for entity_id, entity in moving_entities:
            # Calculate interpolated position
            new_position = get_interpolated_position(
                position=entity["position"],
                velocity=entity["velocity"],
                last_update_time=entity["last_update_time"],
                current_time=current_time,
            )

            # Update spatial index with new position
            if self.simulation.spatial_index:
                self.simulation.spatial_index.update(entity_id, new_position)

    def _log_performance_stats(self) -> None:
        """Log performance statistics."""
        if self.frame_count == 0:
            return

        avg_frame_time = (self.total_frame_time / self.frame_count) * 1000
        target_frame_time = self.frame_time * 1000

        logger.info(
            "MovementSystem performance",
            frames=self.frame_count,
            avg_frame_time_ms=f"{avg_frame_time:.2f}",
            target_ms=f"{target_frame_time:.2f}",
            moving_entities=sum(
                1 for e in self.simulation.state.entities.values()
                if any(v != 0.0 for v in e.get("velocity", (0.0, 0.0, 0.0)))
            ),
        )

        # Reset counters
        self.frame_count = 0
        self.total_frame_time = 0.0
        self.last_stats_time = time.perf_counter()

    def get_entity_position(self, entity_id: UUID) -> Optional[Position]:
        """Get current interpolated position of an entity.

        Args:
            entity_id: Entity UUID

        Returns:
            Current position tuple (x, y, z), or None if entity not found
        """
        entity = self.simulation.state.get_entity(entity_id)
        if not entity:
            return None

        current_time = self.simulation.clock.get_time()

        return get_interpolated_position(
            position=entity["position"],
            velocity=entity["velocity"],
            last_update_time=entity["last_update_time"],
            current_time=current_time,
        )

    async def set_entity_velocity(
        self,
        entity_id: UUID,
        velocity: tuple[float, float, float],
    ) -> None:
        """Set velocity for an entity.

        This emits an ENTITY_MOVED event which updates the entity's velocity
        in the state and records the current position.

        Args:
            entity_id: Entity UUID
            velocity: Velocity vector (vx, vy, vz) in units/second
        """
        entity = self.simulation.state.get_entity(entity_id)
        if not entity:
            logger.warning("Cannot set velocity for non-existent entity", entity_id=str(entity_id))
            return

        current_time = self.simulation.clock.get_time()

        # Calculate current interpolated position before changing velocity
        current_position = get_interpolated_position(
            position=entity["position"],
            velocity=entity["velocity"],
            last_update_time=entity["last_update_time"],
            current_time=current_time,
        )

        # Emit ENTITY_MOVED event with new velocity and current position
        await self.simulation.emit_event(
            event_type=EventType.ENTITY_MOVED,
            data={
                "entity_id": str(entity_id),
                "position": list(current_position),
                "velocity": list(velocity),
            },
        )

        logger.debug(
            "Entity velocity set",
            entity_id=str(entity_id),
            velocity=velocity,
            position=current_position,
        )
