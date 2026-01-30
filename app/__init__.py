# path: app/__init__.py
"""
Telegram AI Group Finance Assistant Platform
A production-ready, multi-tenant, context-aware, spreadsheet-driven finance bot.
"""

__version__ = "1.0.0"
__author__ = "Finance Bot Team"

from app.config.settings import Settings
from app.infra.logger import setup_logger

__all__ = ["Settings", "setup_logger", "__version__"]
