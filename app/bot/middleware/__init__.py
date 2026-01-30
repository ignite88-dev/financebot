# path: app/bot/middleware/__init__.py
"""
Bot middleware module - Authentication and logging middleware.
"""

from app.bot.middleware.auth import AuthMiddleware
from app.bot.middleware.logging import LoggingMiddleware

__all__ = ["AuthMiddleware", "LoggingMiddleware"]
