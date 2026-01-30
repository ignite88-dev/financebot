# path: app/bot/handlers/__init__.py
"""
Bot handlers module - Message, command, and callback handlers.
"""

from app.bot.handlers.message import MessageHandlers
from app.bot.handlers.command import CommandHandlers
from app.bot.handlers.callback import CallbackHandlers
from app.bot.handlers.error import error_handler

__all__ = [
    "MessageHandlers",
    "CommandHandlers",
    "CallbackHandlers",
    "error_handler"
]
