# path: app/bot/handlers/error.py
"""
Error handler for the Telegram bot.
"""

import traceback
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import (
    TelegramError,
    Forbidden,
    BadRequest,
    TimedOut,
    NetworkError
)

from app.infra.logger import get_logger


logger = get_logger(__name__)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle errors that occur during update processing.

    This handler logs errors and sends appropriate responses to users
    when possible.
    """
    error = context.error

    logger.error(f"Exception while handling an update: {error}")

    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = "".join(tb_list)
    logger.error(f"Traceback:\n{tb_string}")

    if isinstance(error, Forbidden):
        logger.warning(
            f"Forbidden error - bot may have been blocked or removed: {error}"
        )
        return

    if isinstance(error, BadRequest):
        if "message is not modified" in str(error).lower():
            logger.debug("Attempted to edit message with same content")
            return

        if "message to edit not found" in str(error).lower():
            logger.warning("Message to edit was not found")
            return

        if "chat not found" in str(error).lower():
            logger.warning("Chat not found - may have been deleted")
            return

        logger.error(f"Bad request error: {error}")

    if isinstance(error, TimedOut):
        logger.warning(f"Request timed out: {error}")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"Network error occurred: {error}")
        return

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Maaf, terjadi kesalahan saat memproses permintaan Anda. "
                "Silakan coba lagi nanti."
            )
        except TelegramError as e:
            logger.error(f"Failed to send error message to user: {e}")

    if isinstance(update, Update):
        update_data = {
            "update_id": update.update_id,
            "message": str(update.effective_message) if update.effective_message else None,
            "user": update.effective_user.id if update.effective_user else None,
            "chat": update.effective_chat.id if update.effective_chat else None
        }
        logger.error(f"Update that caused error: {update_data}")


class ErrorRecovery:
    """Helper class for error recovery strategies."""

    @staticmethod
    async def retry_with_backoff(
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0
    ):
        """
        Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Factor to multiply delay by after each retry
        """
        import asyncio

        delay = initial_delay
        last_error = None

        for attempt in range(max_retries):
            try:
                return await func()
            except (TimedOut, NetworkError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

        raise last_error

    @staticmethod
    def is_recoverable_error(error: Exception) -> bool:
        """Check if an error is potentially recoverable."""
        recoverable_types = (TimedOut, NetworkError)
        return isinstance(error, recoverable_types)

    @staticmethod
    def get_user_friendly_message(error: Exception) -> str:
        """Get a user-friendly error message."""
        if isinstance(error, Forbidden):
            return (
                "Bot tidak memiliki izin untuk melakukan tindakan ini. "
                "Pastikan bot adalah admin grup."
            )

        if isinstance(error, BadRequest):
            return (
                "Permintaan tidak valid. "
                "Silakan periksa format perintah Anda."
            )

        if isinstance(error, TimedOut):
            return (
                "Koneksi timeout. "
                "Silakan coba lagi."
            )

        if isinstance(error, NetworkError):
            return (
                "Terjadi masalah jaringan. "
                "Silakan coba lagi nanti."
            )

        return (
            "Terjadi kesalahan yang tidak terduga. "
            "Silakan coba lagi atau hubungi admin."
        )
