# core/exceptions.py

"""Exception hierarchy for STRATEGOS simulation engine."""


class StrategosException(Exception):
    """Base exception for all STRATEGOS errors."""

    pass


# Event Store Exceptions
class EventStoreException(StrategosException):
    """Base exception for event store operations."""

    pass


class EventPersistenceError(EventStoreException):
    """Raised when an event cannot be persisted to the store."""

    pass


class EventRetrievalError(EventStoreException):
    """Raised when events cannot be retrieved from the store."""

    pass


class EventValidationError(EventStoreException):
    """Raised when an event fails validation."""

    pass


# Checkpoint Exceptions
class CheckpointException(StrategosException):
    """Base exception for checkpoint operations."""

    pass


class CheckpointCreationError(CheckpointException):
    """Raised when a checkpoint cannot be created."""

    pass


class CheckpointRestoreError(CheckpointException):
    """Raised when a checkpoint cannot be restored."""

    pass


class CheckpointNotFoundError(CheckpointException):
    """Raised when a requested checkpoint does not exist."""

    pass


# Simulation Exceptions
class SimulationException(StrategosException):
    """Base exception for simulation operations."""

    pass


class SimulationStateError(SimulationException):
    """Raised when simulation is in an invalid state for the requested operation."""

    pass


class TimeSeekError(SimulationException):
    """Raised when a time seek operation fails."""

    pass


# Event Handler Exceptions
class EventHandlerException(StrategosException):
    """Base exception for event handler operations."""

    pass


class HandlerExecutionError(EventHandlerException):
    """Raised when an event handler fails during execution."""

    pass
