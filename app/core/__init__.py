# path: app/core/__init__.py
"""
Core module - Router, context builder, events, and AI engine.
"""

from app.core.router import MessageRouter
from app.core.context import ContextBuilder
from app.core.events import EventEmitter, Event
from app.core.ai_engine import AIEngine

__all__ = [
    "MessageRouter",
    "ContextBuilder",
    "EventEmitter",
    "Event",
    "AIEngine"
]
