# core/state.py

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID


@dataclass
class WorldState:
    """Current state of the simulation world."""

    simulation_time: float = 0.0
    event_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # Phase 1: Minimal state
    # Later phases will add: entities, economies, etc.

    @property
    def current_time(self) -> float:
        """Alias for simulation_time for compatibility with tests."""
        return self.simulation_time

    @current_time.setter
    def current_time(self, value: float) -> None:
        """Alias setter for simulation_time."""
        self.simulation_time = value

    def apply_event(self, event: "Event") -> None:
        """Apply an event to update world state."""
        self.simulation_time = event.simulation_time
        self.event_count += 1

        # Phase 1: Just track that events happened
        # Later phases: Actually modify entities, resources, etc.


class SimulationState:
    """Container for simulation state including entities and custom data."""

    def __init__(self, simulation_id: UUID):
        """Initialize simulation state."""
        self.simulation_id = simulation_id
        self.current_time: float = 0.0
        self.entities: dict[UUID, dict[str, Any]] = {}
        self.entity_types: dict[str, set[UUID]] = {}
        self.entity_positions: dict[UUID, tuple[float, float, float]] = {}
        self.custom_state: dict[str, Any] = {}

    def add_entity(self, entity_id: UUID, data: dict[str, Any], entity_type: str) -> None:
        """Add an entity to the simulation."""
        self.entities[entity_id] = data
        if entity_type not in self.entity_types:
            self.entity_types[entity_type] = set()
        self.entity_types[entity_type].add(entity_id)

    def remove_entity(self, entity_id: UUID) -> None:
        """Remove an entity from the simulation."""
        if entity_id in self.entities:
            del self.entities[entity_id]

        # Remove from type tracking
        for entity_type in self.entity_types.values():
            entity_type.discard(entity_id)

        # Remove position tracking
        if entity_id in self.entity_positions:
            del self.entity_positions[entity_id]

    def get_entity(self, entity_id: UUID) -> Optional[dict[str, Any]]:
        """Get entity data by ID."""
        return self.entities.get(entity_id)

    def entity_count(self) -> int:
        """Get total entity count."""
        return len(self.entities)

    def get_entities_by_type(self, entity_type: str) -> set[UUID]:
        """Get all entities of a given type."""
        return self.entity_types.get(entity_type, set())

    def update_entity_position(self, entity_id: UUID, x: float, y: float, z: float = 0.0) -> None:
        """Update entity position."""
        if entity_id in self.entities:
            self.entity_positions[entity_id] = (x, y, z)

    def get_entity_position(self, entity_id: UUID) -> tuple[float, float, float]:
        """Get entity position (x, y, z)."""
        return self.entity_positions.get(entity_id, (0.0, 0.0, 0.0))

    def set_custom_state(self, key: str, value: Any) -> None:
        """Set custom state value."""
        self.custom_state[key] = value

    def get_custom_state(self, key: str, default: Any = None) -> Any:
        """Get custom state value."""
        return self.custom_state.get(key, default)

    def clear(self) -> None:
        """Clear all state."""
        self.entities.clear()
        self.entity_types.clear()
        self.entity_positions.clear()
        self.custom_state.clear()
        self.current_time = 0.0
