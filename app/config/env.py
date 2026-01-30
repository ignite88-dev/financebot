# path: app/config/env.py
"""
Environment - Environment variable loading and validation.
"""

import os
from pathlib import Path
from typing import Optional

from app.infra.logger import get_logger


logger = None


def load_environment(env_file: Optional[str] = None) -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file (optional)
    """
    if env_file:
        env_path = Path(env_file)
    else:
        env_path = Path(".env")
        if not env_path.exists():
            env_path = Path(__file__).parent.parent.parent / ".env"

    if env_path.exists():
        _load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")
    else:
        print("No .env file found, using system environment variables")


def _load_dotenv(path: Path) -> None:
    """
    Simple dotenv loader without external dependencies.

    Args:
        path: Path to .env file
    """
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                if key not in os.environ:
                    os.environ[key] = value

    except Exception as e:
        print(f"Error loading .env file: {e}")


def get_env(
    key: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Get an environment variable.

    Args:
        key: Variable name
        default: Default value if not set
        required: Raise error if not set

    Returns:
        Variable value or default
    """
    value = os.getenv(key, default)

    if required and not value:
        raise EnvironmentError(f"Required environment variable not set: {key}")

    return value


def get_env_int(
    key: str,
    default: int = 0,
    required: bool = False
) -> int:
    """
    Get an environment variable as integer.

    Args:
        key: Variable name
        default: Default value if not set
        required: Raise error if not set

    Returns:
        Variable value as integer
    """
    value = get_env(key, required=required)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def get_env_bool(
    key: str,
    default: bool = False
) -> bool:
    """
    Get an environment variable as boolean.

    Args:
        key: Variable name
        default: Default value if not set

    Returns:
        Variable value as boolean
    """
    value = get_env(key)

    if value is None:
        return default

    return value.lower() in ("true", "1", "yes", "on")


def get_env_list(
    key: str,
    default: Optional[list] = None,
    separator: str = ","
) -> list:
    """
    Get an environment variable as list.

    Args:
        key: Variable name
        default: Default value if not set
        separator: List separator

    Returns:
        Variable value as list
    """
    value = get_env(key)

    if value is None:
        return default or []

    return [item.strip() for item in value.split(separator) if item.strip()]


def validate_environment() -> dict:
    """
    Validate that all required environment variables are set.

    Returns:
        Dict with validation results
    """
    required_vars = [
        "TELEGRAM_TOKEN",
        "GOOGLE_CREDENTIALS_PATH",
        "MASTER_SHEET_ID",
        "OPENAI_API_KEY"
    ]

    optional_vars = [
        "SERVICE_ACCOUNT_EMAIL",
        "AI_MODEL",
        "LOG_LEVEL",
        "ENVIRONMENT",
        "DEBUG",
        "SUPER_ADMIN_IDS"
    ]

    results = {
        "valid": True,
        "missing_required": [],
        "missing_optional": [],
        "loaded": []
    }

    for var in required_vars:
        if os.getenv(var):
            results["loaded"].append(var)
        else:
            results["missing_required"].append(var)
            results["valid"] = False

    for var in optional_vars:
        if os.getenv(var):
            results["loaded"].append(var)
        else:
            results["missing_optional"].append(var)

    return results


def print_environment_status() -> None:
    """Print the status of environment variables."""
    results = validate_environment()

    print("\n=== Environment Status ===")
    print(f"Valid: {results['valid']}")

    if results["loaded"]:
        print(f"\nLoaded ({len(results['loaded'])}):")
        for var in results["loaded"]:
            print(f"  ✓ {var}")

    if results["missing_required"]:
        print(f"\nMissing Required ({len(results['missing_required'])}):")
        for var in results["missing_required"]:
            print(f"  ✗ {var}")

    if results["missing_optional"]:
        print(f"\nMissing Optional ({len(results['missing_optional'])}):")
        for var in results["missing_optional"]:
            print(f"  - {var}")

    print("==========================\n")
