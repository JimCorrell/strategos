# core/event_handlers.py

"""Event handler registry for type-specific event subscriptions."""

from collections import defaultdict
from typing import Awaitable, Callable

from .events import Event, EventType
from .exceptions import HandlerExecutionError
from .logging import get_logger

logger = get_logger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class EventHandlerRegistry:
    """Registry for managing type-specific event subscriptions."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self.logger = get_logger(f"{__name__}.EventHandlerRegistry")

    def on(self, event_type: EventType | str, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: The type of event to subscribe to
            handler: Async callable that processes the event
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        self._handlers[event_type_str].append(handler)

        self.logger.debug(
            "handler.registered",
            event_type=event_type_str,
            handler_count=len(self._handlers[event_type_str]),
        )

    def on_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to ALL event types (wildcard subscription).

        Args:
            handler: Async callable that processes any event
        """
        self._wildcard_handlers.append(handler)

        self.logger.debug(
            "handler.registered_wildcard",
            wildcard_handler_count=len(self._wildcard_handlers),
        )

    def off(self, event_type: EventType | str, handler: EventHandler) -> bool:
        """Unsubscribe a handler from a specific event type.

        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove

        Returns:
            True if handler was removed, False if not found
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        if event_type_str in self._handlers and handler in self._handlers[event_type_str]:
            self._handlers[event_type_str].remove(handler)
            self.logger.debug("handler.unregistered", event_type=event_type_str)
            return True

        return False

    def off_all(self, handler: EventHandler) -> bool:
        """Unsubscribe a wildcard handler.

        Args:
            handler: The handler to remove

        Returns:
            True if handler was removed, False if not found
        """
        if handler in self._wildcard_handlers:
            self._wildcard_handlers.remove(handler)
            self.logger.debug("handler.unregistered_wildcard")
            return True

        return False

    async def dispatch(self, event: Event, fail_fast: bool = False) -> None:
        """Dispatch an event to all interested handlers.

        Args:
            event: The event to dispatch
            fail_fast: If True, raise on first handler error. If False, log and continue.

        Raises:
            HandlerExecutionError: If fail_fast=True and a handler raises an exception
        """
        event_type_str = (
            event.event_type.value if isinstance(event.event_type, EventType) else event.event_type
        )

        # Get type-specific handlers
        handlers = self._handlers.get(event_type_str, [])

        # Add wildcard handlers
        all_handlers = handlers + self._wildcard_handlers

        if not all_handlers:
            return

        self.logger.debug(
            "event.dispatching",
            event_type=event_type_str,
            event_id=str(event.event_id),
            handler_count=len(all_handlers),
        )

        errors = []

        for handler in all_handlers:
            try:
                await handler(event)
            except Exception as e:
                error_msg = f"Handler {handler.__name__} failed for event {event.event_id}: {e}"

                self.logger.error(
                    "handler.execution_failed",
                    event_type=event_type_str,
                    event_id=str(event.event_id),
                    handler=handler.__name__,
                    error=str(e),
                )

                if fail_fast:
                    raise HandlerExecutionError(error_msg) from e
                else:
                    errors.append((handler, e))

        if errors:
            self.logger.warning(
                "event.dispatch_completed_with_errors",
                event_type=event_type_str,
                event_id=str(event.event_id),
                error_count=len(errors),
            )

    def get_handler_count(self, event_type: EventType | str | None = None) -> int:
        """Get the number of handlers registered.

        Args:
            event_type: If provided, count handlers for this type only.
                       If None, count all handlers including wildcards.

        Returns:
            Number of registered handlers
        """
        if event_type is None:
            # Count all handlers
            total = sum(len(handlers) for handlers in self._handlers.values())
            total += len(self._wildcard_handlers)
            return total
        else:
            event_type_str = (
                event_type.value if isinstance(event_type, EventType) else event_type
            )
            return len(self._handlers.get(event_type_str, []))

    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()
        self._wildcard_handlers.clear()
        self.logger.info("handlers.cleared")
