# path: app/persona/prompts.py
"""
Prompt Builder - Builds dynamic system prompts for AI.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.infra.logger import get_logger


logger = get_logger(__name__)


class PromptBuilder:
    """
    Builds dynamic system prompts for AI based on context.
    """

    BASE_PROMPT = """Kamu adalah asisten keuangan AI untuk grup Telegram.

KEMAMPUAN UTAMA:
- Mencatat transaksi keuangan (pemasukan dan pengeluaran)
- Memberikan informasi saldo dan laporan keuangan
- Menjawab pertanyaan seputar keuangan grup
- Membantu perencanaan anggaran

ATURAN PENTING:
1. Selalu gunakan Bahasa Indonesia
2. Berikan respons yang relevan dengan konteks keuangan
3. Jika diminta mencatat transaksi, konfirmasi dengan format yang jelas
4. Jangan pernah mengungkapkan informasi sensitif
5. Jika tidak yakin, minta klarifikasi"""

    FINANCIAL_CONTEXT_TEMPLATE = """
KONTEKS KEUANGAN GRUP:
- Saldo saat ini: {balance}
- Total pemasukan: {total_income}
- Total pengeluaran: {total_expense}
- Jumlah transaksi: {transaction_count}"""

    RECENT_TRANSACTIONS_TEMPLATE = """
TRANSAKSI TERAKHIR:
{transactions}"""

    USER_CONTEXT_TEMPLATE = """
TENTANG PENGGUNA:
- Username: {username}
- Total transaksi: {user_transaction_count}
- Aktivitas: {activity_level}"""

    def __init__(self):
        self._templates: Dict[str, str] = {}

    def build_system_prompt(
        self,
        persona_prompt: str,
        group_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        financial_context: Optional[Dict[str, Any]] = None,
        recent_transactions: Optional[List[Dict[str, Any]]] = None,
        additional_instructions: Optional[str] = None
    ) -> str:
        """
        Build a complete system prompt.

        Args:
            persona_prompt: The persona's base system prompt
            group_context: Group information
            user_context: User information
            financial_context: Financial summary
            recent_transactions: Recent transactions
            additional_instructions: Extra instructions

        Returns:
            Complete system prompt
        """
        prompt_parts = [
            self.BASE_PROMPT,
            "",
            "PERSONA:",
            persona_prompt
        ]

        if group_context:
            prompt_parts.append("")
            prompt_parts.append(self._format_group_context(group_context))

        if financial_context:
            prompt_parts.append("")
            prompt_parts.append(self._format_financial_context(financial_context))

        if recent_transactions:
            prompt_parts.append("")
            prompt_parts.append(self._format_recent_transactions(recent_transactions))

        if user_context:
            prompt_parts.append("")
            prompt_parts.append(self._format_user_context(user_context))

        prompt_parts.append("")
        prompt_parts.append(f"WAKTU SAAT INI: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if additional_instructions:
            prompt_parts.append("")
            prompt_parts.append("INSTRUKSI TAMBAHAN:")
            prompt_parts.append(additional_instructions)

        return "\n".join(prompt_parts)

    def _format_group_context(self, context: Dict[str, Any]) -> str:
        """Format group context."""
        parts = ["KONTEKS GRUP:"]

        if context.get("group_name"):
            parts.append(f"- Nama grup: {context['group_name']}")

        if context.get("member_count"):
            parts.append(f"- Jumlah anggota: {context['member_count']}")

        if context.get("created_at"):
            parts.append(f"- Dibuat: {context['created_at']}")

        if context.get("language"):
            parts.append(f"- Bahasa: {context['language']}")

        return "\n".join(parts)

    def _format_financial_context(self, context: Dict[str, Any]) -> str:
        """Format financial context."""
        balance = context.get("balance", 0)
        total_income = context.get("total_income", 0)
        total_expense = context.get("total_expense", 0)
        transaction_count = context.get("transaction_count", 0)

        return self.FINANCIAL_CONTEXT_TEMPLATE.format(
            balance=f"Rp {balance:,.0f}",
            total_income=f"Rp {total_income:,.0f}",
            total_expense=f"Rp {total_expense:,.0f}",
            transaction_count=transaction_count
        )

    def _format_recent_transactions(
        self,
        transactions: List[Dict[str, Any]]
    ) -> str:
        """Format recent transactions."""
        if not transactions:
            return ""

        tx_lines = []
        for tx in transactions[:5]:
            tx_type = "+" if tx.get("type") == "income" else "-"
            amount = tx.get("amount", 0)
            desc = tx.get("description", "")[:30]
            tx_lines.append(f"  {tx_type} Rp {amount:,.0f} - {desc}")

        return self.RECENT_TRANSACTIONS_TEMPLATE.format(
            transactions="\n".join(tx_lines)
        )

    def _format_user_context(self, context: Dict[str, Any]) -> str:
        """Format user context."""
        username = context.get("username", "Unknown")
        tx_count = context.get("transaction_count", 0)

        if tx_count > 50:
            activity = "Sangat aktif"
        elif tx_count > 20:
            activity = "Aktif"
        elif tx_count > 5:
            activity = "Cukup aktif"
        else:
            activity = "Baru"

        return self.USER_CONTEXT_TEMPLATE.format(
            username=username,
            user_transaction_count=tx_count,
            activity_level=activity
        )

    def build_transaction_prompt(
        self,
        tx_type: str,
        amount: float,
        description: str
    ) -> str:
        """
        Build a prompt for transaction confirmation.

        Args:
            tx_type: Transaction type
            amount: Transaction amount
            description: Transaction description

        Returns:
            Prompt for AI to confirm transaction
        """
        type_label = "pemasukan" if tx_type == "income" else "pengeluaran"

        return f"""User ingin mencatat {type_label}:
- Jumlah: Rp {amount:,.0f}
- Keterangan: {description}

Konfirmasi transaksi ini dengan format yang jelas dan ramah sesuai persona."""

    def build_report_prompt(
        self,
        period: str,
        report_data: Dict[str, Any]
    ) -> str:
        """
        Build a prompt for report generation.

        Args:
            period: Report period (week/month/year)
            report_data: Report data

        Returns:
            Prompt for AI to generate report summary
        """
        period_label = {
            "week": "minggu ini",
            "month": "bulan ini",
            "year": "tahun ini"
        }.get(period, period)

        return f"""Berikan ringkasan laporan keuangan {period_label}:

Data:
- Total Pemasukan: Rp {report_data.get('total_income', 0):,.0f}
- Total Pengeluaran: Rp {report_data.get('total_expense', 0):,.0f}
- Saldo: Rp {report_data.get('balance', 0):,.0f}
- Jumlah Transaksi: {report_data.get('transaction_count', 0)}

Berikan insight singkat tentang kondisi keuangan grup."""

    def build_query_prompt(
        self,
        user_query: str,
        context_type: str = "general"
    ) -> str:
        """
        Build a prompt for user query.

        Args:
            user_query: The user's question
            context_type: Type of context (general/financial/help)

        Returns:
            Prompt for AI response
        """
        context_instructions = {
            "general": "Jawab pertanyaan ini dengan ramah dan informatif.",
            "financial": "Ini adalah pertanyaan tentang keuangan. Berikan jawaban yang akurat berdasarkan data yang tersedia.",
            "help": "User membutuhkan bantuan. Jelaskan dengan jelas dan berikan contoh jika diperlukan."
        }

        instruction = context_instructions.get(context_type, context_instructions["general"])

        return f"""{instruction}

Pertanyaan user: {user_query}"""

    def add_custom_template(
        self,
        name: str,
        template: str
    ) -> None:
        """
        Add a custom template.

        Args:
            name: Template name
            template: Template string
        """
        self._templates[name] = template

    def get_template(self, name: str) -> Optional[str]:
        """
        Get a custom template.

        Args:
            name: Template name

        Returns:
            Template string or None
        """
        return self._templates.get(name)

    def format_custom_template(
        self,
        name: str,
        **kwargs
    ) -> Optional[str]:
        """
        Format a custom template with values.

        Args:
            name: Template name
            **kwargs: Template values

        Returns:
            Formatted template or None
        """
        template = self._templates.get(name)
        if not template:
            return None

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing template key: {e}")
            return None
