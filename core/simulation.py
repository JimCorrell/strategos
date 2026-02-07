# core/simulation.py

from typing import TYPE_CHECKING, Awaitable, Callable, Optional
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from spatial import MovementSystem, SpatialIndex

from .checkpoints import Checkpoint, CheckpointStore
from .event_handlers import EventHandler, EventHandlerRegistry
from .event_store import EventStore
from .events import Event, EventType, EventValidator
from .exceptions import EventValidationError, SimulationStateError
from .logging import get_logger
from .state import WorldState
from .time import SimulationClock


class Simulation:
    """Main simulation orchestrator."""

    def __init__(
        self,
        db_path: str,
        checkpoint_dir: str,
        checkpoint_interval: float = 1.0,
        time_scale: float = 1.0,
        simulation_id: Optional[UUID] = None,
    ):
        self.simulation_id = simulation_id or uuid4()
        self.event_store = EventStore(db_path)
        self.checkpoint_store = CheckpointStore(checkpoint_dir, checkpoint_interval)
        self.checkpoint_manager = self.checkpoint_store  # Alias for compatibility
        self.clock = SimulationClock(time_scale)
        self.state = WorldState()
        self.logger = get_logger(f"{__name__}.Simulation")
        self._initialized = False
        self._running = False

        # Event handler registry for type-specific subscriptions
        self._event_handlers = EventHandlerRegistry()

        # Phase 2: Spatial subsystems
        self.spatial_index: Optional["SpatialIndex"] = None
        self.movement_system: Optional["MovementSystem"] = None

    async def initialize(self) -> None:
        """Initialize the simulation components."""
        await self.event_store.initialize()

        # Phase 2: Initialize spatial subsystems
        from spatial import MovementSystem, SpatialIndex

        self.spatial_index = SpatialIndex()
        await self.spatial_index.initialize(self)

        self.movement_system = MovementSystem(self)
        await self.movement_system.initialize()

        self._initialized = True

        self.logger.info(
            "simulation.initialized",
            simulation_id=str(self.simulation_id),
            time_scale=self.clock.time_scale,
            checkpoint_interval=self.checkpoint_store.checkpoint_interval,
        )

    async def shutdown(self) -> None:
        """Shutdown the simulation and close resources."""
        if self._running:
            await self.stop()
        await self.event_store.close()
        self._initialized = False
        self.logger.info("simulation.shutdown", simulation_id=str(self.simulation_id))

    async def start(self, time_scale: float | None = None) -> None:
        """Start the simulation from current state.

        Args:
            time_scale: Optional time scale to set before starting
        """
        if self._running:
            return  # Already running

        if time_scale is not None:
            await self.set_time_scale(time_scale)

        self._running = True
        await self.clock.start()

        # Phase 2b: Start movement system
        if self.movement_system:
            await self.movement_system.start()

        await self.emit_event(
            EventType.SIMULATION_STARTED,
            {"simulation_id": str(self.simulation_id), "time_scale": self.clock.time_scale},
        )

        self.logger.info(
            "simulation.started",
            simulation_id=str(self.simulation_id),
            current_time=self.clock.get_time(),
        )

    async def stop(self) -> None:
        """Stop the simulation completely."""
        if not self._running:
            return

        self._running = False

        # Phase 2b: Stop movement system
        if self.movement_system:
            await self.movement_system.stop()

        await self.clock.stop()
        self.logger.info("simulation.stopped", simulation_id=str(self.simulation_id))

    async def pause(self) -> None:
        """Pause the simulation."""
        if not self._running:
            return

        self._running = False
        await self.clock.pause()
        await self.emit_event(
            EventType.SIMULATION_PAUSED,
            {"simulation_id": str(self.simulation_id), "paused_at": self.clock.get_time()},
        )

        self.logger.info(
            "simulation.paused",
            simulation_id=str(self.simulation_id),
            paused_at=self.clock.get_time(),
        )

    async def resume(self) -> None:
        """Resume a paused simulation."""
        self._running = True
        await self.clock.resume()
        self.logger.info("simulation.resumed", simulation_id=str(self.simulation_id))

    async def seek(self, target_time: float) -> None:
        """Rewind or fast-forward to a specific time."""
        start_time = self.clock.get_time()

        self.logger.info("simulation.seek.started", from_time=start_time, to_time=target_time)

        # Find nearest checkpoint before target
        checkpoint = await self.checkpoint_store.get_nearest_before(target_time)

        if checkpoint:
            self.state = checkpoint.deserialize_state()
            replay_from = checkpoint.simulation_time
            self.logger.debug(
                "simulation.seek.using_checkpoint",
                checkpoint_time=checkpoint.simulation_time,
            )
        else:
            self.state = WorldState()
            replay_from = 0.0
            self.logger.debug("simulation.seek.full_replay")

        # Replay events
        events = await self.event_store.get_events(from_time=replay_from, to_time=target_time)
        events_replayed = 0
        for event in events:
            self.state.apply_event(event)
            events_replayed += 1

        await self.clock.seek(target_time)

        self.logger.info(
            "simulation.seek.completed",
            from_time=start_time,
            to_time=target_time,
            events_replayed=events_replayed,
        )

    async def emit_event(self, event_type: EventType | str, data: dict) -> Event:
        """Create and store a new event.

        Args:
            event_type: Type of event to create
            data: Event data payload

        Returns:
            The created event

        Raises:
            EventValidationError: If event fails validation
        """
        event = Event(
            event_type=event_type,
            simulation_time=self.clock.get_time(),
            data=data,
        )

        # Validate event before processing
        EventValidator.validate(event)

        self.logger.debug(
            "event.emitting",
            event_type=event_type.value if isinstance(event_type, EventType) else event_type,
            event_id=str(event.event_id),
        )

        # Persist event
        await self.event_store.append(event)

        # Apply to current state
        self.state.apply_event(event)

        # Dispatch to registered handlers
        await self._event_handlers.dispatch(event, fail_fast=False)

        # Maybe checkpoint
        if self.checkpoint_store.should_create_checkpoint(self.clock.get_time()):
            checkpoint = Checkpoint.create(
                simulation_time=self.clock.get_time(),
                state=self.state,
            )
            await self.checkpoint_store.save(checkpoint)

        return event

    async def set_time_scale(self, scale: float) -> None:
        """Change simulation speed."""
        old_scale = self.clock.time_scale
        await self.clock.set_time_scale(scale)

        await self.emit_event(EventType.TIME_SCALED, {"old_scale": old_scale, "new_scale": scale})

        self.logger.info("time.scale_changed", old_scale=old_scale, new_scale=scale)

    async def create_marker(self, label: str, metadata: dict | None = None) -> Event:
        """Create a timestamped marker event (useful for testing/debugging)."""
        return await self.emit_event(
            EventType.MARKER_CREATED, {"label": label, "metadata": metadata or {}}
        )

    def add_event_listener(self, listener: EventHandler) -> None:
        """Subscribe to ALL events for streaming (backwards compatible).

        Args:
            listener: Async callable that receives all events
        """
        self._event_handlers.on_all(listener)

    def on_event(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Subscribe to specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async callable that receives matching events
        """
        self._event_handlers.on(event_type, handler)

    def off_event(self, event_type: EventType | str, handler: EventHandler) -> bool:
        """Unsubscribe from specific event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler to remove

        Returns:
            True if handler was removed, False if not found
        """
        return self._event_handlers.off(event_type, handler)

    def get_status(self) -> dict:
        """Get current simulation status."""
        return {
            "simulation_id": str(self.simulation_id),
            "current_time": self.clock.get_time(),
            "time_scale": self.clock.time_scale,
            "is_running": self._running,
            "running": self._running,  # Alias for compatibility
            "clock_state": self.clock.get_state().value,
            "state": self.clock.get_state().value,  # Alias for clock_state
            "event_count": self.state.event_count,
            "entity_count": len(self.state.entities),  # Phase 2: Actual entity count
            "formatted_time": self.clock.format_time(),
        }

    # Phase 2: Entity Lifecycle Methods

    async def create_entity(
        self,
        entity_type: str,
        position: tuple[float, float, float] | list[float],
        max_speed: float = 10.0,
        metadata: dict | None = None,
    ) -> UUID:
        """Create a new entity in the simulation.

        Args:
            entity_type: Type of entity (e.g., "infantry", "tank")
            position: Initial (x, y, z) coordinates
            max_speed: Maximum speed in meters/second
            metadata: Optional additional metadata

        Returns:
            UUID of created entity
        """
        entity_id = uuid4()

        # Normalize position to tuple
        if isinstance(position, list):
            position = tuple(position)
        if len(position) == 2:
            position = (position[0], position[1], 0.0)

        await self.emit_event(
            EventType.ENTITY_CREATED,
            {
                "entity_id": str(entity_id),
                "type": entity_type,
                "position": list(position),
                "max_speed": max_speed,
                "metadata": metadata or {},
            },
        )

        self.logger.info(
            "entity.created",
            entity_id=str(entity_id),
            entity_type=entity_type,
            position=position,
        )

        return entity_id

    async def destroy_entity(self, entity_id: UUID) -> None:
        """Destroy an entity.

        Args:
            entity_id: UUID of entity to destroy
        """
        await self.emit_event(
            EventType.ENTITY_DESTROYED,
            {"entity_id": str(entity_id)},
        )

        self.logger.info("entity.destroyed", entity_id=str(entity_id))

    def query_entities_in_radius(
        self,
        center: tuple[float, float, float],
        radius: float,
        include_z: bool = False,
    ) -> list[UUID]:
        """Find all entities within radius of center point.

        Args:
            center: Center position (x, y, z)
            radius: Search radius
            include_z: If True, use 3D distance; if False, use 2D (x, y only)

        Returns:
            List of entity UUIDs within radius
        """
        if self.spatial_index is None:
            return []

        return self.spatial_index.query_radius(center, radius, include_z)

    def get_entity(self, entity_id: UUID) -> Optional[dict]:
        """Get entity data by ID.

        Args:
            entity_id: Entity UUID

        Returns:
            Entity data dictionary or None if not found
        """
        return self.state.get_entity(entity_id)

    def get_entities_by_type(self, entity_type: str) -> set[UUID]:
        """Get all entities of a given type.

        Args:
            entity_type: Entity type to query

        Returns:
            Set of entity UUIDs
        """
        return self.state.get_entities_by_type(entity_type)

    async def set_entity_velocity(
        self,
        entity_id: UUID,
        velocity: tuple[float, float, float],
    ) -> None:
        """Set velocity for an entity (Phase 2b).

        Args:
            entity_id: Entity UUID
            velocity: Velocity vector (vx, vy, vz) in units/second
        """
        if self.movement_system is None:
            self.logger.warning("Cannot set velocity: movement system not initialized")
            return

        await self.movement_system.set_entity_velocity(entity_id, velocity)

    def get_entity_position(self, entity_id: UUID) -> Optional[tuple[float, float, float]]:
        """Get current interpolated position of an entity.

        Args:
            entity_id: Entity UUID

        Returns:
            Current position tuple (x, y, z), or None if entity not found
        """
        if self.movement_system is None:
            # Fallback to state position if movement system not initialized
            entity = self.get_entity(entity_id)
            return entity["position"] if entity else None

        return self.movement_system.get_entity_position(entity_id)
