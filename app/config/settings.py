# path: app/config/settings.py
"""
Settings - Application configuration with validation.
"""

import os
from typing import Optional, List
from dataclasses import dataclass, field
from pathlib import Path

from app.infra.exceptions import ConfigurationError


@dataclass
class Settings:
    """
    Application settings loaded from environment variables.
    """

    telegram_token: str = ""

    google_credentials_path: str = ""
    service_account_email: str = ""
    master_sheet_id: str = ""

    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 1000
    ai_temperature: float = 0.7

    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None

    environment: str = "development"
    debug: bool = False

    memory_max_messages: int = 50
    context_window_size: int = 10

    default_language: str = "id"
    default_persona: str = "professional"
    default_currency: str = "IDR"
    default_timezone: str = "Asia/Jakarta"

    super_admin_ids: List[int] = field(default_factory=list)

    rate_limit_messages: int = 30
    rate_limit_window: int = 60

    webhook_url: Optional[str] = None
    webhook_port: int = 8443

    def __post_init__(self):
        """Validate settings after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate required settings."""
        errors = []

        if not self.telegram_token:
            errors.append("TELEGRAM_TOKEN is required")

        if not self.google_credentials_path:
            errors.append("GOOGLE_CREDENTIALS_PATH is required")
        elif not Path(self.google_credentials_path).exists():
            if self.environment != "test":
                errors.append(
                    f"Google credentials file not found: {self.google_credentials_path}"
                )

        if not self.master_sheet_id:
            errors.append("MASTER_SHEET_ID is required")

        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")

        if errors and self.environment != "test":
            raise ConfigurationError(
                "Configuration errors:\n" + "\n".join(f"- {e}" for e in errors)
            )

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        super_admin_ids_str = os.getenv("SUPER_ADMIN_IDS", "")
        super_admin_ids = []
        if super_admin_ids_str:
            try:
                super_admin_ids = [
                    int(id.strip())
                    for id in super_admin_ids_str.split(",")
                    if id.strip()
                ]
            except ValueError:
                pass

        return cls(
            telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
            google_credentials_path=os.getenv(
                "GOOGLE_CREDENTIALS_PATH",
                "credentials.json"
            ),
            service_account_email=os.getenv("SERVICE_ACCOUNT_EMAIL", ""),
            master_sheet_id=os.getenv("MASTER_SHEET_ID", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            ai_model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            ai_max_tokens=int(os.getenv("AI_MAX_TOKENS", "1000")),
            ai_temperature=float(os.getenv("AI_TEMPERATURE", "0.7")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            memory_max_messages=int(os.getenv("MEMORY_MAX_MESSAGES", "50")),
            context_window_size=int(os.getenv("CONTEXT_WINDOW_SIZE", "10")),
            default_language=os.getenv("DEFAULT_LANGUAGE", "id"),
            default_persona=os.getenv("DEFAULT_PERSONA", "professional"),
            default_currency=os.getenv("DEFAULT_CURRENCY", "IDR"),
            default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Jakarta"),
            super_admin_ids=super_admin_ids,
            rate_limit_messages=int(os.getenv("RATE_LIMIT_MESSAGES", "30")),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", "60")),
            webhook_url=os.getenv("WEBHOOK_URL"),
            webhook_port=int(os.getenv("WEBHOOK_PORT", "8443"))
        )

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "ai_model": self.ai_model,
            "log_level": self.log_level,
            "default_language": self.default_language,
            "default_persona": self.default_persona,
            "memory_max_messages": self.memory_max_messages,
            "context_window_size": self.context_window_size
        }


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings.from_env()
    return _settings
