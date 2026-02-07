# core/events.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class EventValidationError(Exception):
    """Raised when event validation fails."""

    pass


class EventType(str, Enum):
    """Event type enumeration."""

    SIMULATION_STARTED = "simulation.started"
    SIMULATION_PAUSED = "simulation.paused"
    SIMULATION_RESUMED = "simulation.resumed"
    SIMULATION_STOPPED = "simulation.stopped"
    TIME_SCALED = "time.scaled"
    TIME_SCALE_CHANGED = "simulation.time_scale_changed"
    MARKER_CREATED = "marker.created"
    ENTITY_CREATED = "entity.created"
    ENTITY_MOVED = "entity.moved"
    ENTITY_DESTROYED = "entity.destroyed"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"


@dataclass(frozen=True)
class Event:
    """Immutable event representing a state change."""

    event_type: EventType | str
    simulation_time: float = 0.0  # Simulation time in seconds
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)
    causation_id: Optional[UUID] = None  # What event caused this
    correlation_id: Optional[UUID] = None  # Group related events
    created_at: Optional[datetime] = None  # Real-world timestamp

    def __post_init__(self):
        # Convert string to EventType if needed
        if isinstance(self.event_type, str):
            try:
                object.__setattr__(self, "event_type", EventType(self.event_type))
            except ValueError:
                # Keep as string if not a known EventType
                pass

        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))

    def __hash__(self) -> int:
        """Make events hashable for use in sets/deduplication."""
        return hash(self.event_id)

    @property
    def timestamp(self) -> datetime:
        """Get the event's creation timestamp."""
        return self.created_at or datetime.now(timezone.utc)

    @classmethod
    def create(
        cls,
        simulation_time: float,
        event_type: EventType | str,
        data: dict[str, Any],
        causation_id: Optional[UUID] = None,
    ) -> "Event":
        """Factory method for creating events."""
        return cls(
            simulation_time=simulation_time,
            event_type=event_type,
            data=data,
            causation_id=causation_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            "event_id": str(self.event_id),
            "simulation_time": self.simulation_time,
            "event_type": (
                self.event_type.value if isinstance(self.event_type, EventType) else self.event_type
            ),
            "data": self.data,
            "metadata": self.metadata,
            "causation_id": str(self.causation_id) if self.causation_id else None,
            "correlation_id": str(self.correlation_id) if self.correlation_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Create event from dictionary representation."""
        return cls(
            event_id=UUID(data["event_id"]),
            simulation_time=data["simulation_time"],
            event_type=data["event_type"],
            data=data["data"],
            metadata=data.get("metadata", {}),
            causation_id=UUID(data["causation_id"]) if data.get("causation_id") else None,
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            created_at=(
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
            ),
        )


class EventValidator:
    """Lightweight validator for event data."""

    # Define required fields for each event type
    SCHEMAS: dict[str, dict[str, Any]] = {
        EventType.SIMULATION_STARTED: {
            "required": ["simulation_id", "time_scale"],
            "types": {"simulation_id": str, "time_scale": (int, float)},
        },
        EventType.SIMULATION_PAUSED: {
            "required": ["simulation_id", "paused_at"],
            "types": {"simulation_id": str, "paused_at": (int, float)},
        },
        EventType.SIMULATION_STOPPED: {
            "required": ["simulation_id"],
            "types": {"simulation_id": str},
        },
        EventType.TIME_SCALED: {
            "required": ["old_scale", "new_scale"],
            "types": {"old_scale": (int, float), "new_scale": (int, float)},
        },
        EventType.MARKER_CREATED: {
            "required": ["label"],
            "types": {"label": str},
        },
        EventType.ENTITY_CREATED: {
            "required": ["entity_id", "type"],
            "types": {"entity_id": str, "type": str},
        },
        EventType.ENTITY_MOVED: {
            "required": ["entity_id"],
            "types": {"entity_id": str},
        },
        EventType.ENTITY_DESTROYED: {
            "required": ["entity_id"],
            "types": {"entity_id": str},
        },
    }

    @classmethod
    def validate(cls, event: Event) -> None:
        """Validate event data against schema.

        Args:
            event: Event to validate

        Raises:
            EventValidationError: If validation fails
        """
        event_type = event.event_type

        # Convert string to EventType if needed for lookup
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type)
            except ValueError:
                # Unknown event type - skip validation
                return

        schema = cls.SCHEMAS.get(event_type)
        if not schema:
            # No schema defined - skip validation
            return

        # Check required fields
        required_fields = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in event.data:
                raise EventValidationError(
                    f"Event {event_type.value} missing required field: {field_name}"
                )

        # Check field types
        type_specs = schema.get("types", {})
        for field_name, expected_type in type_specs.items():
            if field_name in event.data:
                value = event.data[field_name]
                if not isinstance(value, expected_type):
                    raise EventValidationError(
                        f"Event {event_type.value} field '{field_name}' has wrong type: "
                        f"expected {expected_type}, got {type(value)}"
                    )

    @classmethod
    def is_valid(cls, event: Event) -> bool:
        """Check if event is valid without raising exceptions.

        Args:
            event: Event to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            cls.validate(event)
            return True
        except EventValidationError:
            return False
