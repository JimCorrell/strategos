# Phase 1 Refactoring Suggestions

## 1. **Immutable Events (✅ Already Done)**

Your new `Event` dataclass with `@dataclass(frozen=True)` is excellent - immutability is critical for event sourcing.

**Suggestion:** Add `__hash__` to make events hashable for deduplication:

```python
def __hash__(self):
    return hash(self.event_id)
```

---

## 2. **Event Correlation & Causation (✅ Already Done)**

Great addition of `causation_id` and `correlation_id` for tracing event chains and grouping related events.

**Suggestion:** Add event metadata helpers:

```python
def with_correlation_id(self, correlation_id: UUID) -> "Event":
    """Create a new event with correlation ID."""
    return replace(self, correlation_id=correlation_id)
```

---

## 3. **Structured Logging via structlog (✅ Already Done)**

Using structlog is perfect for event sourcing - structured logs match event structure.

**Suggestion:** Add logging to key simulation points:

- Event emission/application
- Checkpoint creation/restoration
- Seek operations
- State changes

Example:

```python
logger = structlog.get_logger(__name__)

async def emit_event(self, event_type: str, data: dict) -> Event:
    event = Event.create(...)
    logger.info("event_emitted", event_type=event_type, event_id=str(event.event_id))
    await self.event_store.append(event)
```

---

## 4. **Dependency Injection Pattern**

Currently components are tightly coupled. Consider a factory or DI container:

**Before:**

```python
simulation = Simulation(uuid4(), event_store, checkpoint_store)
```

**After:**

```python
class SimulationFactory:
    @staticmethod
    def create(config: SimulationConfig) -> Simulation:
        event_store = EventStore(config.db_path)
        checkpoint_store = CheckpointStore(config.checkpoint_dir)
        return Simulation(uuid4(), event_store, checkpoint_store)
```

Benefits:

- Easier testing and mocking
- Clearer component lifecycle
- Configuration centralization

---

## 5. **Event Handler Registry**

The `_event_listeners` list is good, but could be more structured:

**Current:**

```python
self._event_listeners: list[callable] = []
```

**Suggested:**

```python
class EventHandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, list[callable]] = defaultdict(list)

    def on(self, event_type: str, handler: callable):
        """Subscribe to specific event type."""
        self._handlers[event_type].append(handler)

    async def dispatch(self, event: Event):
        """Dispatch event to interested handlers."""
        for handler in self._handlers.get(event.event_type, []):
            await handler(event)
```

This allows:

- Type-specific subscriptions
- Better performance filtering
- Clearer intent

---

## 6. **Error Handling & Recovery**

Add resilience patterns:

```python
class EventStoreException(Exception):
    """Base exception for event store operations."""
    pass

class EventPersistenceError(EventStoreException):
    """Raised when event cannot be persisted."""
    pass

async def emit_event(self, event_type: str, data: dict) -> Event:
    try:
        event = Event.create(...)
        await self.event_store.append(event)
    except EventPersistenceError as e:
        logger.error("event_emission_failed", error=str(e), event_type=event_type)
        raise
```

---

## 7. **Checkpoint Versioning**

As the system evolves, checkpoints from old code versions may not deserialize:

```python
@dataclass
class Checkpoint:
    version: int  # Schema version
    timestamp: float
    state: bytes

    def is_compatible(self, current_version: int) -> bool:
        return self.version <= current_version
```

---

## 8. **Event Validation**

Add schema validation:

```python
class EventValidator:
    SCHEMAS: dict[str, dict] = {
        "entity.created": {
            "required": ["entity_id", "type"],
            "properties": {
                "entity_id": {"type": "string"},
                "type": {"type": "string"},
            }
        }
    }

    @classmethod
    def validate(cls, event: Event) -> bool:
        schema = cls.SCHEMAS.get(event.event_type)
        if not schema:
            return True  # Unknown types pass through
        # Validate against schema
```

---

## 9. **Performance: Batch Event Appending**

For high-throughput scenarios:

```python
async def append_batch(self, events: list[Event]) -> None:
    """Append multiple events atomically."""
    async with self._transaction:
        for event in events:
            await self.append(event)
```

---

## 10. **Testing: Add Logging Verification**

Update tests to verify logging occurs:

```python
@pytest.mark.asyncio
async def test_event_emission_logged(simulation, caplog):
    """Verify event emissions are logged."""
    with caplog.at_level(logging.INFO):
        event = await simulation.emit_event("entity.created", {"id": "123"})

    # Verify log entry
    assert any("event_emitted" in record.message for record in caplog.records)
```

---

## 11. **Configuration Management**

Create a config module:

```python
# config.py
from dataclasses import dataclass

@dataclass
class SimulationConfig:
    db_path: str = "strategos.db"
    checkpoint_dir: str = "checkpoints"
    checkpoint_interval: float = 3600.0
    log_level: str = "INFO"
    time_scale: float = 1.0

    @classmethod
    def from_env(cls) -> "SimulationConfig":
        """Load from environment variables."""
        return cls(
            db_path=os.getenv("STRATEGOS_DB_PATH", cls.db_path),
            # ... etc
        )
```

---

## 12. **Monitoring & Metrics**

Add instrumentation:

```python
class SimulationMetrics:
    def __init__(self):
        self.events_emitted = 0
        self.events_applied = 0
        self.checkpoints_created = 0
        self.seek_operations = 0

    def record_event_emitted(self):
        self.events_emitted += 1
        logger.info("simulation_metric",
                   metric="events_emitted",
                   value=self.events_emitted)
```

---

## Priority Recommendations

**High Priority (before Phase 2):**

1. ✅ Structured logging integration
2. Event handler registry (type-specific subscriptions)
3. Error handling patterns
4. Configuration management
5. Logging verification in tests

**Medium Priority (before release):** 6. Dependency injection pattern 7. Event validation 8. Checkpoint versioning 9. Monitoring/metrics

**Low Priority (Phase 3+):** 10. Batch event operations 11. Advanced resilience patterns

---

## Summary

Your codebase is well-structured! The key improvements would be:

1. **Better event routing** via handler registry
2. **Centralized configuration**
3. **Comprehensive logging** with verification tests
4. **Error handling patterns** for resilience
5. **Optional: DI pattern** for cleaner testing

Would you like me to implement any of these refactorings?
