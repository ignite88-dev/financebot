# path: app/infra/logger.py
"""
Logger - Logging configuration and utilities.
"""

import logging
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime


_initialized = False
_log_level = logging.INFO


class ColorFormatter(logging.Formatter):
    """
    Custom formatter with color support for console output.
    """

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "RESET": "\033[0m"
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Setup the application logger.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        format_string: Optional custom format string
    """
    global _initialized, _log_level

    if _initialized:
        return

    _log_level = getattr(logging, level.upper(), logging.INFO)

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(_log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_log_level)

    if sys.stdout.isatty():
        console_formatter = ColorFormatter(format_string)
    else:
        console_formatter = logging.Formatter(format_string)

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(_log_level)
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)

    _initialized = True

    root_logger.info(f"Logger initialized with level: {level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    if not _initialized:
        setup_logger()

    return logging.getLogger(name)


class LogContext:
    """
    Context manager for logging with additional context.
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        **context
    ):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[datetime] = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(
            f"Starting {self.operation}",
            extra={"context": self.context}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type:
            self.logger.error(
                f"Failed {self.operation} after {duration:.2f}s: {exc_val}",
                extra={"context": self.context}
            )
        else:
            self.logger.debug(
                f"Completed {self.operation} in {duration:.2f}s",
                extra={"context": self.context}
            )

        return False


class AsyncLogContext:
    """
    Async context manager for logging.
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        **context
    ):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time: Optional[datetime] = None

    async def __aenter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting {self.operation}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type:
            self.logger.error(
                f"Failed {self.operation} after {duration:.2f}s: {exc_val}"
            )
        else:
            self.logger.debug(f"Completed {self.operation} in {duration:.2f}s")

        return False


def log_function_call(logger: logging.Logger):
    """
    Decorator to log function calls.

    Args:
        logger: Logger instance to use
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"Completed {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger.debug(f"Calling {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Completed {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
