# path: app/core/events.py
"""
Event system for decoupled component communication.
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from app.infra.logger import get_logger


logger = get_logger(__name__)


class EventType(Enum):
    """Enumeration of event types in the system."""

    GROUP_CREATED = "group.created"
    GROUP_ACTIVATED = "group.activated"
    GROUP_DEACTIVATED = "group.deactivated"
    GROUP_RESET = "group.reset"

    TRANSACTION_ADDED = "transaction.added"
    TRANSACTION_UPDATED = "transaction.updated"
    TRANSACTION_DELETED = "transaction.deleted"

    USER_JOINED = "user.joined"
    USER_LEFT = "user.left"
    USER_PROMOTED = "user.promoted"

    MESSAGE_RECEIVED = "message.received"
    MESSAGE_PROCESSED = "message.processed"

    ONBOARDING_STARTED = "onboarding.started"
    ONBOARDING_COMPLETED = "onboarding.completed"
    ONBOARDING_FAILED = "onboarding.failed"

    SETTINGS_CHANGED = "settings.changed"
    PERSONA_CHANGED = "persona.changed"

    REPORT_GENERATED = "report.generated"

    ERROR_OCCURRED = "error.occurred"


@dataclass
class Event:
    """Represents an event in the system."""

    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    chat_id: Optional[int] = None
    user_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "chat_id": self.chat_id,
            "user_id": self.user_id
        }


EventHandler = Callable[[Event], Any]


class EventEmitter:
    """
    Event emitter for publishing and subscribing to events.
    """

    _instance: Optional['EventEmitter'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._async_handlers: Dict[EventType, List[EventHandler]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._initialized = True

    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        is_async: bool = True
    ) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: The handler function to call
            is_async: Whether the handler is async
        """
        if is_async:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

        logger.debug(f"Subscribed handler to {event_type.value}")

    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> None:
        """
        Unsubscribe from an event type.
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

        if event_type in self._async_handlers:
            self._async_handlers[event_type] = [
                h for h in self._async_handlers[event_type] if h != handler
            ]

    async def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event: The event to emit
        """
        logger.debug(f"Emitting event: {event.event_type.value}")

        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        sync_handlers = self._handlers.get(event.event_type, [])
        for handler in sync_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in sync event handler: {e}")

        async_handlers = self._async_handlers.get(event.event_type, [])
        if async_handlers:
            tasks = [
                self._safe_call_handler(handler, event)
                for handler in async_handlers
            ]
            await asyncio.gather(*tasks)

    async def _safe_call_handler(
        self,
        handler: EventHandler,
        event: Event
    ) -> None:
        """Safely call an async handler."""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Error in async event handler: {e}")

    async def emit_transaction_added(
        self,
        chat_id: int,
        user_id: int,
        transaction_data: Dict[str, Any]
    ) -> None:
        """Emit a transaction added event."""
        event = Event(
            event_type=EventType.TRANSACTION_ADDED,
            data=transaction_data,
            chat_id=chat_id,
            user_id=user_id,
            source="transaction_service"
        )
        await self.emit(event)

    async def emit_group_activated(
        self,
        chat_id: int,
        user_id: int,
        group_data: Dict[str, Any]
    ) -> None:
        """Emit a group activated event."""
        event = Event(
            event_type=EventType.GROUP_ACTIVATED,
            data=group_data,
            chat_id=chat_id,
            user_id=user_id,
            source="onboarding"
        )
        await self.emit(event)

    async def emit_error(
        self,
        error_type: str,
        error_message: str,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Emit an error event."""
        event = Event(
            event_type=EventType.ERROR_OCCURRED,
            data={
                "error_type": error_type,
                "error_message": error_message,
                **(additional_data or {})
            },
            chat_id=chat_id,
            user_id=user_id,
            source="error_handler"
        )
        await self.emit(event)

    def get_recent_events(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[Event]:
        """
        Get recent events from history.

        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return
        """
        events = self._event_history

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


def get_event_emitter() -> EventEmitter:
    """Get the singleton event emitter instance."""
    return EventEmitter()


def on_event(event_type: EventType):
    """
    Decorator to register a function as an event handler.

    Usage:
        @on_event(EventType.TRANSACTION_ADDED)
        async def handle_transaction(event: Event):
            print(f"Transaction added: {event.data}")
    """
    def decorator(func: EventHandler):
        emitter = get_event_emitter()
        emitter.subscribe(event_type, func, is_async=asyncio.iscoroutinefunction(func))
        return func
    return decorator
