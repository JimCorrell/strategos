"""Core simulation engine components."""

from .checkpoints import Checkpoint, CheckpointStore
from .event_handlers import EventHandler, EventHandlerRegistry
from .event_store import EventStore
from .events import Event, EventType, EventValidator
from .exceptions import (
    CheckpointCreationError,
    CheckpointException,
    CheckpointNotFoundError,
    CheckpointRestoreError,
    EventHandlerException,
    EventPersistenceError,
    EventRetrievalError,
    EventStoreException,
    EventValidationError,
    HandlerExecutionError,
    SimulationException,
    SimulationStateError,
    StrategosException,
    TimeSeekError,
)
from .simulation import Simulation
from .state import SimulationState
from .time import SimulationClock

__all__ = [
    # Core classes
    "Event",
    "EventType",
    "EventValidator",
    "EventStore",
    "CheckpointStore",
    "Checkpoint",
    "SimulationClock",
    "SimulationState",
    "Simulation",
    "EventHandler",
    "EventHandlerRegistry",
    # Exceptions
    "StrategosException",
    "EventStoreException",
    "EventPersistenceError",
    "EventRetrievalError",
    "EventValidationError",
    "CheckpointException",
    "CheckpointCreationError",
    "CheckpointRestoreError",
    "CheckpointNotFoundError",
    "SimulationException",
    "SimulationStateError",
    "TimeSeekError",
    "EventHandlerException",
    "HandlerExecutionError",
]
