# path: app/bot/middleware/logging.py
"""
Logging middleware for tracking bot activities.
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from app.infra.logger import get_logger


logger = get_logger(__name__)


class LoggingMiddleware:
    """
    Middleware for logging bot activities and metrics.
    """

    def __init__(self):
        self._request_count: int = 0
        self._error_count: int = 0
        self._start_time: datetime = datetime.now()
        self._metrics: Dict[str, Any] = {
            "commands": {},
            "messages": 0,
            "callbacks": 0,
            "errors": 0
        }

    async def log_update(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        handler_name: str,
        duration_ms: float
    ) -> None:
        """
        Log an update that was processed.

        Args:
            update: The Telegram update object
            context: The context object
            handler_name: Name of the handler that processed the update
            duration_ms: Processing duration in milliseconds
        """
        self._request_count += 1

        user_id = update.effective_user.id if update.effective_user else None
        chat_id = update.effective_chat.id if update.effective_chat else None
        chat_type = update.effective_chat.type if update.effective_chat else None

        log_data = {
            "update_id": update.update_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "chat_type": chat_type,
            "handler": handler_name,
            "duration_ms": round(duration_ms, 2)
        }

        if update.message:
            if update.message.text and update.message.text.startswith("/"):
                command = update.message.text.split()[0]
                log_data["command"] = command
                self._metrics["commands"][command] = (
                    self._metrics["commands"].get(command, 0) + 1
                )
            else:
                self._metrics["messages"] += 1
                log_data["message_length"] = len(update.message.text or "")

        elif update.callback_query:
            self._metrics["callbacks"] += 1
            log_data["callback_data"] = update.callback_query.data

        logger.info(f"Update processed: {log_data}")

    async def log_error(
        self,
        update: Optional[Update],
        error: Exception,
        handler_name: str
    ) -> None:
        """
        Log an error that occurred during update processing.
        """
        self._error_count += 1
        self._metrics["errors"] += 1

        error_data = {
            "update_id": update.update_id if update else None,
            "user_id": update.effective_user.id if update and update.effective_user else None,
            "chat_id": update.effective_chat.id if update and update.effective_chat else None,
            "handler": handler_name,
            "error_type": type(error).__name__,
            "error_message": str(error)
        }

        logger.error(f"Error in handler: {error_data}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics.
        """
        uptime = datetime.now() - self._start_time

        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "error_rate": (
                self._error_count / self._request_count
                if self._request_count > 0 else 0
            ),
            "uptime_seconds": uptime.total_seconds(),
            "commands": self._metrics["commands"],
            "total_messages": self._metrics["messages"],
            "total_callbacks": self._metrics["callbacks"]
        }

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._request_count = 0
        self._error_count = 0
        self._start_time = datetime.now()
        self._metrics = {
            "commands": {},
            "messages": 0,
            "callbacks": 0,
            "errors": 0
        }


def log_handler(handler_name: str):
    """
    Decorator to log handler execution.

    Args:
        handler_name: Name of the handler for logging purposes
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args,
            **kwargs
        ):
            start_time = time.time()

            try:
                result = await func(self, update, context, *args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000

                logging_middleware = getattr(self, "logging_middleware", None)
                if logging_middleware:
                    await logging_middleware.log_update(
                        update, context, handler_name, duration_ms
                    )

                return result

            except Exception as e:
                logging_middleware = getattr(self, "logging_middleware", None)
                if logging_middleware:
                    await logging_middleware.log_error(
                        update, e, handler_name
                    )
                raise

        return wrapper
    return decorator


class RequestLogger:
    """
    Context manager for logging request duration.
    """

    def __init__(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        self.operation = operation
        self.metadata = metadata or {}
        self.start_time: float = 0

    async def __aenter__(self):
        self.start_time = time.time()
        logger.debug(f"Starting {self.operation}: {self.metadata}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type:
            logger.error(
                f"Failed {self.operation} after {duration_ms:.2f}ms: "
                f"{exc_type.__name__}: {exc_val}"
            )
        else:
            logger.debug(
                f"Completed {self.operation} in {duration_ms:.2f}ms"
            )

        return False


class AuditLogger:
    """
    Logger for audit-critical operations.
    """

    def __init__(self, sheets_client=None):
        self.sheets_client = sheets_client

    async def log_action(
        self,
        action: str,
        user_id: int,
        chat_id: int,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an auditable action.

        Args:
            action: The action performed
            user_id: The user who performed the action
            chat_id: The chat where the action was performed
            details: Additional details about the action
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "chat_id": chat_id,
            "details": details or {}
        }

        logger.info(f"AUDIT: {audit_entry}")

        if self.sheets_client:
            try:
                pass
            except Exception as e:
                logger.error(f"Failed to write audit log to sheets: {e}")

    async def log_transaction(
        self,
        transaction_id: str,
        user_id: int,
        chat_id: int,
        tx_type: str,
        amount: float,
        description: str
    ) -> None:
        """
        Log a financial transaction.
        """
        await self.log_action(
            action="transaction",
            user_id=user_id,
            chat_id=chat_id,
            details={
                "transaction_id": transaction_id,
                "type": tx_type,
                "amount": amount,
                "description": description
            }
        )

    async def log_settings_change(
        self,
        user_id: int,
        chat_id: int,
        setting: str,
        old_value: Any,
        new_value: Any
    ) -> None:
        """
        Log a settings change.
        """
        await self.log_action(
            action="settings_change",
            user_id=user_id,
            chat_id=chat_id,
            details={
                "setting": setting,
                "old_value": old_value,
                "new_value": new_value
            }
        )
