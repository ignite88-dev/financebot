# path: app/persona/style.py
"""
Style Formatter - Formats responses according to persona style.
"""

from typing import Dict, Any, Optional
from enum import Enum

from app.infra.logger import get_logger


logger = get_logger(__name__)


class ResponseStyle(Enum):
    """Available response styles."""
    FORMAL = "formal"
    CASUAL = "casual"
    MINIMAL = "minimal"
    ENTHUSIASTIC = "enthusiastic"
    CUSTOM = "custom"


class StyleFormatter:
    """
    Formats bot responses according to the active style.
    """

    STYLE_CONFIGS = {
        "formal": {
            "use_emoji": False,
            "greeting_prefix": "Selamat",
            "thank_you": "Terima kasih",
            "confirmation": "Baik, telah dicatat",
            "error_prefix": "Mohon maaf",
            "bullet_style": "•",
            "number_format": "Rp {:,.0f}",
            "capitalize_headers": True,
            "line_spacing": "single"
        },
        "casual": {
            "use_emoji": True,
            "greeting_prefix": "Hai",
            "thank_you": "Thanks",
            "confirmation": "Oke, udah dicatat",
            "error_prefix": "Waduh",
            "bullet_style": "→",
            "number_format": "Rp {:,.0f}",
            "capitalize_headers": False,
            "line_spacing": "single"
        },
        "minimal": {
            "use_emoji": False,
            "greeting_prefix": "",
            "thank_you": "OK",
            "confirmation": "Tercatat",
            "error_prefix": "Error:",
            "bullet_style": "-",
            "number_format": "{:,.0f}",
            "capitalize_headers": False,
            "line_spacing": "compact"
        },
        "enthusiastic": {
            "use_emoji": True,
            "greeting_prefix": "Halo",
            "thank_you": "Makasih banget",
            "confirmation": "Mantap! Sudah dicatat",
            "error_prefix": "Oops",
            "bullet_style": "✓",
            "number_format": "Rp {:,.0f}",
            "capitalize_headers": True,
            "line_spacing": "single"
        }
    }

    STYLE_EMOJIS = {
        "formal": {},
        "casual": {
            "income": "📈",
            "expense": "📉",
            "balance": "💰",
            "report": "📊",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "greeting": "👋",
            "celebration": "🎉"
        },
        "minimal": {},
        "enthusiastic": {
            "income": "🤑📈",
            "expense": "💸📉",
            "balance": "💰✨",
            "report": "📊🔥",
            "success": "✅🎉",
            "error": "❌😅",
            "warning": "⚠️👀",
            "info": "💡",
            "greeting": "👋🌟",
            "celebration": "🎉🎊"
        }
    }

    def __init__(self, style: str = "formal"):
        self.style = style
        self.config = self.STYLE_CONFIGS.get(style, self.STYLE_CONFIGS["formal"])
        self.emojis = self.STYLE_EMOJIS.get(style, {})

    def set_style(self, style: str) -> None:
        """
        Set the formatting style.

        Args:
            style: The style name
        """
        self.style = style
        self.config = self.STYLE_CONFIGS.get(style, self.STYLE_CONFIGS["formal"])
        self.emojis = self.STYLE_EMOJIS.get(style, {})

    def format_currency(self, amount: float) -> str:
        """
        Format a currency amount.

        Args:
            amount: The amount to format

        Returns:
            Formatted currency string
        """
        format_str = self.config.get("number_format", "Rp {:,.0f}")
        return format_str.format(amount)

    def format_header(self, text: str) -> str:
        """
        Format a header/title.

        Args:
            text: The header text

        Returns:
            Formatted header
        """
        if self.config.get("capitalize_headers"):
            text = text.upper()

        return f"<b>{text}</b>"

    def format_list_item(self, text: str, index: Optional[int] = None) -> str:
        """
        Format a list item.

        Args:
            text: The item text
            index: Optional numeric index

        Returns:
            Formatted list item
        """
        bullet = self.config.get("bullet_style", "•")

        if index is not None:
            return f"{index}. {text}"

        return f"{bullet} {text}"

    def format_transaction(
        self,
        tx_type: str,
        amount: float,
        description: str
    ) -> str:
        """
        Format a transaction message.

        Args:
            tx_type: Transaction type (income/expense)
            amount: Transaction amount
            description: Transaction description

        Returns:
            Formatted transaction message
        """
        emoji = self.get_emoji(tx_type)
        type_label = "Pemasukan" if tx_type == "income" else "Pengeluaran"

        confirmation = self.config.get("confirmation", "Tercatat")

        lines = [
            f"{emoji} {self.format_header(confirmation)}" if emoji else self.format_header(confirmation),
            "",
            f"Tipe: {type_label}",
            f"Jumlah: {self.format_currency(amount)}",
            f"Keterangan: {description}"
        ]

        return "\n".join(lines)

    def format_balance(
        self,
        total_income: float,
        total_expense: float,
        balance: float
    ) -> str:
        """
        Format a balance message.

        Args:
            total_income: Total income
            total_expense: Total expense
            balance: Current balance

        Returns:
            Formatted balance message
        """
        emoji = self.get_emoji("balance")
        header = f"{emoji} Saldo Grup" if emoji else "Saldo Grup"

        lines = [
            self.format_header(header),
            "",
            f"Pemasukan: {self.format_currency(total_income)}",
            f"Pengeluaran: {self.format_currency(total_expense)}",
            "━━━━━━━━━━━━",
            f"<b>Saldo: {self.format_currency(balance)}</b>"
        ]

        return "\n".join(lines)

    def format_error(self, message: str) -> str:
        """
        Format an error message.

        Args:
            message: The error message

        Returns:
            Formatted error message
        """
        prefix = self.config.get("error_prefix", "Error")
        emoji = self.get_emoji("error")

        if emoji:
            return f"{emoji} {prefix}, {message}"

        return f"{prefix}, {message}"

    def format_success(self, message: str) -> str:
        """
        Format a success message.

        Args:
            message: The success message

        Returns:
            Formatted success message
        """
        emoji = self.get_emoji("success")

        if emoji:
            return f"{emoji} {message}"

        return message

    def format_greeting(self, username: Optional[str] = None) -> str:
        """
        Format a greeting.

        Args:
            username: Optional username

        Returns:
            Formatted greeting
        """
        prefix = self.config.get("greeting_prefix", "Halo")
        emoji = self.get_emoji("greeting")

        if username:
            greeting = f"{prefix} {username}!"
        else:
            greeting = f"{prefix}!"

        if emoji:
            greeting = f"{emoji} {greeting}"

        return greeting

    def get_emoji(self, category: str) -> str:
        """
        Get emoji for a category.

        Args:
            category: The emoji category

        Returns:
            Emoji string or empty string
        """
        if not self.config.get("use_emoji"):
            return ""

        return self.emojis.get(category, "")

    def format_report_section(
        self,
        title: str,
        items: list,
        show_numbers: bool = True
    ) -> str:
        """
        Format a report section.

        Args:
            title: Section title
            items: List of items
            show_numbers: Whether to show numbers

        Returns:
            Formatted section
        """
        lines = [self.format_header(title), ""]

        for i, item in enumerate(items, 1):
            if show_numbers:
                lines.append(self.format_list_item(item, i))
            else:
                lines.append(self.format_list_item(item))

        return "\n".join(lines)

    def apply_line_spacing(self, text: str) -> str:
        """
        Apply line spacing based on style.

        Args:
            text: The text to format

        Returns:
            Text with appropriate spacing
        """
        spacing = self.config.get("line_spacing", "single")

        if spacing == "compact":
            lines = text.split("\n")
            lines = [l for l in lines if l.strip()]
            return "\n".join(lines)

        return text

    def wrap_message(
        self,
        content: str,
        title: Optional[str] = None,
        footer: Optional[str] = None
    ) -> str:
        """
        Wrap content with optional title and footer.

        Args:
            content: The main content
            title: Optional title
            footer: Optional footer

        Returns:
            Wrapped message
        """
        parts = []

        if title:
            parts.append(self.format_header(title))
            parts.append("")

        parts.append(content)

        if footer:
            parts.append("")
            parts.append(f"<i>{footer}</i>")

        return self.apply_line_spacing("\n".join(parts))
