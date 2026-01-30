# path: app/infra/utils.py
"""
Utils - Utility functions for the application.
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


def format_currency(
    amount: float,
    currency: str = "IDR",
    include_symbol: bool = True
) -> str:
    """
    Format a number as currency.

    Args:
        amount: The amount to format
        currency: Currency code
        include_symbol: Whether to include currency symbol

    Returns:
        Formatted currency string
    """
    symbols = {
        "IDR": "Rp",
        "USD": "$",
        "EUR": "€",
        "SGD": "S$"
    }

    decimals = {
        "IDR": 0,
        "USD": 2,
        "EUR": 2,
        "SGD": 2
    }

    decimal_places = decimals.get(currency, 0)

    if decimal_places == 0:
        formatted = f"{amount:,.0f}"
    else:
        formatted = f"{amount:,.{decimal_places}f}"

    if include_symbol:
        symbol = symbols.get(currency, currency)
        return f"{symbol} {formatted}"

    return formatted


def format_date(
    date: datetime,
    format_type: str = "short"
) -> str:
    """
    Format a datetime object.

    Args:
        date: The datetime to format
        format_type: Format type (short, long, datetime)

    Returns:
        Formatted date string
    """
    formats = {
        "short": "%d/%m/%Y",
        "long": "%d %B %Y",
        "datetime": "%d/%m/%Y %H:%M",
        "time": "%H:%M",
        "iso": "%Y-%m-%d"
    }

    fmt = formats.get(format_type, formats["short"])
    return date.strftime(fmt)


def format_relative_time(
    date: datetime,
    now: Optional[datetime] = None
) -> str:
    """
    Format a datetime as relative time.

    Args:
        date: The datetime
        now: Current time (defaults to now)

    Returns:
        Relative time string
    """
    if now is None:
        now = datetime.now()

    diff = now - date

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} tahun lalu"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} bulan lalu"
    elif diff.days > 0:
        return f"{diff.days} hari lalu"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} jam lalu"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} menit lalu"
    else:
        return "baru saja"


def extract_amount(text: str) -> Optional[float]:
    """
    Extract a numeric amount from text.

    Args:
        text: Text containing a number

    Returns:
        Extracted amount or None
    """
    text = text.replace("Rp", "").replace("IDR", "")

    text = text.replace(".", "").replace(",", "")

    text = text.strip()

    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:jt|juta)",
        r"(\d+(?:\.\d+)?)\s*(?:rb|ribu|k)",
        r"(\d+(?:[.,]\d+)?)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(",", ".")

            try:
                amount = float(num_str)

                if "jt" in text.lower() or "juta" in text.lower():
                    amount *= 1_000_000
                elif "rb" in text.lower() or "ribu" in text.lower() or "k" in text.lower():
                    amount *= 1_000

                return amount
            except ValueError:
                continue

    return None


def detect_transaction_intent(text: str) -> Optional[Dict[str, Any]]:
    """
    Detect transaction intent from natural language.

    Args:
        text: The text to analyze

    Returns:
        Dict with type and amount, or None
    """
    text_lower = text.lower()

    income_keywords = [
        "terima", "dapat", "masuk", "received", "income",
        "pemasukan", "iuran", "donasi", "sumbangan"
    ]

    expense_keywords = [
        "bayar", "beli", "keluar", "spent", "expense",
        "pengeluaran", "buat", "untuk"
    ]

    tx_type = None

    for keyword in income_keywords:
        if keyword in text_lower:
            tx_type = "income"
            break

    if not tx_type:
        for keyword in expense_keywords:
            if keyword in text_lower:
                tx_type = "expense"
                break

    if not tx_type:
        return None

    amount = extract_amount(text)

    if not amount:
        return None

    return {
        "type": tx_type,
        "amount": amount,
        "description": text[:100]
    }


def sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Sanitize text for storage/display.

    Args:
        text: Text to sanitize
        max_length: Maximum length

    Returns:
        Sanitized text
    """
    text = text.strip()

    text = re.sub(r"<[^>]+>", "", text)

    text = re.sub(r"\s+", " ", text)

    if len(text) > max_length:
        text = text[:max_length - 3] + "..."

    return text


def validate_spreadsheet_url(url: str) -> Optional[str]:
    """
    Validate and extract spreadsheet ID from URL.

    Args:
        url: The URL to validate

    Returns:
        Spreadsheet ID or None
    """
    patterns = [
        r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)",
        r"spreadsheets/d/([a-zA-Z0-9-_]+)",
        r"^([a-zA-Z0-9-_]{20,})$"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def chunk_list(lst: list, chunk_size: int) -> List[list]:
    """
    Split a list into chunks.

    Args:
        lst: The list to split
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [
        lst[i:i + chunk_size]
        for i in range(0, len(lst), chunk_size)
    ]


def truncate_text(
    text: str,
    max_length: int = 100,
    suffix: str = "..."
) -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def parse_period(period: str) -> Dict[str, datetime]:
    """
    Parse a period string into start and end dates.

    Args:
        period: Period string (today, week, month, year)

    Returns:
        Dict with start and end dates
    """
    now = datetime.now()

    periods = {
        "today": {
            "start": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "end": now
        },
        "week": {
            "start": now - timedelta(days=7),
            "end": now
        },
        "month": {
            "start": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            "end": now
        },
        "year": {
            "start": now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
            "end": now
        }
    }

    return periods.get(period.lower(), periods["month"])


def escape_html(text: str) -> str:
    """
    Escape HTML special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;"
    }

    for char, replacement in replacements.items():
        text = text.replace(char, replacement)

    return text


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID.

    Args:
        prefix: Optional prefix

    Returns:
        Unique ID string
    """
    import uuid

    uid = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    if prefix:
        return f"{prefix}_{timestamp}_{uid}"

    return f"{timestamp}_{uid}"
