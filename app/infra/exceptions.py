# path: app/infra/exceptions.py
"""
Exceptions - Custom exception classes for the application.
"""

from typing import Optional, Dict, Any


class FinanceBotError(Exception):
    """
    Base exception for all Finance Bot errors.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ConfigurationError(FinanceBotError):
    """
    Raised when there is a configuration problem.
    """

    def __init__(
        self,
        message: str,
        missing_keys: Optional[list] = None
    ):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            details={"missing_keys": missing_keys or []}
        )


class StartupError(FinanceBotError):
    """
    Raised when the application fails to start.
    """

    def __init__(self, message: str, component: Optional[str] = None):
        super().__init__(
            message=message,
            code="STARTUP_ERROR",
            details={"component": component}
        )


class SheetsError(FinanceBotError):
    """
    Raised when there is a Google Sheets API error.
    """

    def __init__(
        self,
        message: str,
        spreadsheet_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="SHEETS_ERROR",
            details={
                "spreadsheet_id": spreadsheet_id,
                "operation": operation
            }
        )


class SheetNotFoundError(SheetsError):
    """
    Raised when a spreadsheet or sheet is not found.
    """

    def __init__(
        self,
        message: str,
        spreadsheet_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            spreadsheet_id=spreadsheet_id,
            operation="get"
        )
        self.code = "SHEET_NOT_FOUND"


class AIEngineError(FinanceBotError):
    """
    Raised when there is an AI/LLM error.
    """

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            code="AI_ENGINE_ERROR",
            details={
                "model": model,
                "retry_after": retry_after
            }
        )


class AuthorizationError(FinanceBotError):
    """
    Raised when a user is not authorized.
    """

    def __init__(
        self,
        message: str,
        user_id: Optional[int] = None,
        required_role: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details={
                "user_id": user_id,
                "required_role": required_role
            }
        )


class RateLimitError(FinanceBotError):
    """
    Raised when rate limit is exceeded.
    """

    def __init__(
        self,
        message: str,
        retry_after: int = 60
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            details={"retry_after": retry_after}
        )
        self.retry_after = retry_after


class ValidationError(FinanceBotError):
    """
    Raised when input validation fails.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={
                "field": field,
                "value": str(value) if value is not None else None
            }
        )


class TransactionError(FinanceBotError):
    """
    Raised when a transaction operation fails.
    """

    def __init__(
        self,
        message: str,
        transaction_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="TRANSACTION_ERROR",
            details={
                "transaction_id": transaction_id,
                "operation": operation
            }
        )


class OnboardingError(FinanceBotError):
    """
    Raised when onboarding fails.
    """

    def __init__(
        self,
        message: str,
        chat_id: Optional[int] = None,
        state: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="ONBOARDING_ERROR",
            details={
                "chat_id": chat_id,
                "state": state
            }
        )


class MemoryError(FinanceBotError):
    """
    Raised when there is a memory operation error.
    """

    def __init__(
        self,
        message: str,
        chat_id: Optional[int] = None,
        operation: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code="MEMORY_ERROR",
            details={
                "chat_id": chat_id,
                "operation": operation
            }
        )


def handle_exception(error: Exception) -> Dict[str, Any]:
    """
    Convert any exception to a standardized error response.

    Args:
        error: The exception to handle

    Returns:
        Error dictionary
    """
    if isinstance(error, FinanceBotError):
        return error.to_dict()

    return {
        "error": "INTERNAL_ERROR",
        "message": str(error),
        "details": {
            "type": type(error).__name__
        }
    }


def get_user_friendly_message(error: Exception) -> str:
    """
    Get a user-friendly error message.

    Args:
        error: The exception

    Returns:
        User-friendly message in Indonesian
    """
    messages = {
        "CONFIGURATION_ERROR": "Terjadi kesalahan konfigurasi sistem.",
        "SHEETS_ERROR": "Gagal mengakses spreadsheet. Silakan coba lagi.",
        "SHEET_NOT_FOUND": "Spreadsheet tidak ditemukan.",
        "AI_ENGINE_ERROR": "Gagal memproses dengan AI. Silakan coba lagi.",
        "AUTHORIZATION_ERROR": "Anda tidak memiliki izin untuk melakukan ini.",
        "RATE_LIMIT_ERROR": "Terlalu banyak permintaan. Tunggu sebentar.",
        "VALIDATION_ERROR": "Data yang dikirim tidak valid.",
        "TRANSACTION_ERROR": "Gagal memproses transaksi.",
        "ONBOARDING_ERROR": "Gagal melakukan setup. Silakan coba lagi.",
        "MEMORY_ERROR": "Gagal mengakses memory.",
        "INTERNAL_ERROR": "Terjadi kesalahan internal. Silakan coba lagi."
    }

    if isinstance(error, FinanceBotError):
        return messages.get(error.code, messages["INTERNAL_ERROR"])

    return messages["INTERNAL_ERROR"]
