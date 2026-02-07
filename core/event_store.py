# core/event_store.py (updated with logging)

from typing import AsyncIterator, Optional
from uuid import UUID
import aiosqlite
import json
from .events import Event, EventType
from .exceptions import EventPersistenceError, EventRetrievalError
from .logging import get_logger

# Constants
_NOT_INITIALIZED_ERROR = "_NOT_INITIALIZED_ERROR"


class EventStore:
    """Append-only event log with replay capability."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self.logger = get_logger(f"{__name__}.EventStore")

    async def initialize(self) -> None:
        """Initialize the database connection and schema."""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                simulation_time REAL NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                metadata TEXT NOT NULL,
                causation_id TEXT,
                correlation_id TEXT,
                created_at TEXT NOT NULL
            )
        """
        )
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def append(self, event: Event) -> None:
        """Append event to store.

        Args:
            event: Event to persist

        Raises:
            EventPersistenceError: If event cannot be persisted
        """
        if not self._db:
            raise EventPersistenceError("_NOT_INITIALIZED_ERROR")

        try:
            await self._db.execute(
                """
                INSERT INTO events (
                    event_id, simulation_time, event_type, data, metadata,
                    causation_id, correlation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(event.event_id),
                    event.simulation_time,
                    (
                        event.event_type.value
                        if isinstance(event.event_type, EventType)
                        else event.event_type
                    ),
                    json.dumps(event.data),
                    json.dumps(event.metadata),
                    str(event.causation_id) if event.causation_id else None,
                    str(event.correlation_id) if event.correlation_id else None,
                    event.created_at.isoformat(),
                ),
            )
            await self._db.commit()

            self.logger.debug(
                "event.appended",
                event_id=str(event.event_id),
                event_type=(
                    event.event_type.value
                    if isinstance(event.event_type, EventType)
                    else event.event_type
                ),
                simulation_time=event.simulation_time,
            )
        except Exception as e:
            self.logger.error(
                "event.append_failed",
                event_id=str(event.event_id),
                error=str(e),
            )
            raise EventPersistenceError(f"Failed to persist event {event.event_id}: {e}") from e

    async def append_batch(self, events: list[Event]) -> None:
        """Efficiently append multiple events.

        Args:
            events: List of events to persist

        Raises:
            EventPersistenceError: If events cannot be persisted
        """
        if not events:
            return

        if not self._db:
            raise EventPersistenceError("_NOT_INITIALIZED_ERROR")

        try:
            await self._db.executemany(
                """
                INSERT INTO events (
                    event_id, simulation_time, event_type, data, metadata,
                    causation_id, correlation_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        str(e.event_id),
                        e.simulation_time,
                        e.event_type.value if isinstance(e.event_type, EventType) else e.event_type,
                        json.dumps(e.data),
                        json.dumps(e.metadata),
                        str(e.causation_id) if e.causation_id else None,
                        str(e.correlation_id) if e.correlation_id else None,
                        e.created_at.isoformat(),
                    )
                    for e in events
                ],
            )
            await self._db.commit()

            self.logger.info(
                "events.batch_appended",
                batch_size=len(events),
                first_simulation_time=events[0].simulation_time,
                last_simulation_time=events[-1].simulation_time,
            )
        except Exception as e:
            self.logger.error(
                "events.batch_append_failed",
                batch_size=len(events),
                error=str(e),
            )
            raise EventPersistenceError(f"Failed to persist batch of {len(events)} events: {e}") from e

    async def get_events(
        self,
        from_time: float = 0.0,
        to_time: Optional[float] = None,
        event_types: Optional[list[str]] = None,
    ) -> list[Event]:
        """Get events in simulation time order.

        Args:
            from_time: Start time (inclusive)
            to_time: End time (inclusive), None for all future events
            event_types: Filter by event types, None for all types

        Returns:
            List of events matching criteria

        Raises:
            EventRetrievalError: If events cannot be retrieved
        """
        if not self._db:
            raise EventRetrievalError("_NOT_INITIALIZED_ERROR")

        try:
            query = "SELECT * FROM events WHERE simulation_time >= ?"
            params: list = [from_time]

            if to_time is not None:
                query += " AND simulation_time <= ?"
                params.append(to_time)

            if event_types:
                placeholders = ",".join("?" * len(event_types))
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)

            query += " ORDER BY simulation_time ASC, created_at ASC"

            self.logger.debug(
                "events.querying",
                from_time=from_time,
                to_time=to_time,
                event_types=event_types,
            )

            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()

            events = []
            for row in rows:
                from datetime import datetime

                events.append(
                    Event(
                        event_id=UUID(row[0]),
                        simulation_time=row[1],
                        event_type=EventType(row[2]),
                        data=json.loads(row[3]),
                        metadata=json.loads(row[4]),
                        causation_id=UUID(row[5]) if row[5] else None,
                        correlation_id=UUID(row[6]) if row[6] else None,
                        created_at=datetime.fromisoformat(row[7]),
                    )
                )

            self.logger.debug("events.query_complete", events_returned=len(events))
            return events
        except Exception as e:
            self.logger.error(
                "events.query_failed",
                from_time=from_time,
                to_time=to_time,
                error=str(e),
            )
            raise EventRetrievalError(f"Failed to retrieve events: {e}") from e

    async def stream_events(
        self,
        from_time: float = 0.0,
        to_time: Optional[float] = None,
        event_types: Optional[list[str]] = None,
    ) -> AsyncIterator[Event]:
        """Stream events in simulation time order."""
        events = await self.get_events(from_time, to_time, event_types)
        for event in events:
            yield event

    async def get_event_count(self) -> int:
        """Get total number of events."""
        if not self._db:
            return 0
        cursor = await self._db.execute("SELECT COUNT(*) FROM events")
        result = await cursor.fetchone()
        return result[0] if result else 0

    async def clear(self) -> None:
        """Clear all events (for testing)."""
        if not self._db:
            return
        await self._db.execute("DELETE FROM events")
        await self._db.commit()

    async def get_latest_time(self) -> Optional[float]:
        """Get the simulation time of the most recent event."""
        if not self._db:
            return None
        cursor = await self._db.execute("SELECT MAX(simulation_time) FROM events")
        result = await cursor.fetchone()
        return result[0] if result and result[0] is not None else None
