# path: app/core/router.py
"""
Message router - Routes messages to appropriate handlers and generates AI responses.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from app.core.context import ContextBuilder
from app.core.ai_engine import AIEngine
from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.sheets.group import GroupSheet
from app.infra.logger import get_logger
from app.infra.utils import extract_amount, detect_transaction_intent


logger = get_logger(__name__)


class MessageRouter:
    """
    Routes incoming messages to appropriate handlers.
    Handles both AI-powered responses and command-like natural language.
    """

    def __init__(
        self,
        ai_engine: AIEngine,
        context_builder: ContextBuilder,
        sheets_client: SheetsClient,
        master_sheet: MasterSheet
    ):
        self.ai_engine = ai_engine
        self.context_builder = context_builder
        self.sheets_client = sheets_client
        self.master_sheet = master_sheet

        self._intent_patterns = self._compile_intent_patterns()

    def _compile_intent_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for intent detection."""
        return {
            "add_income": re.compile(
                r"(?:catat|tambah|masuk|terima|income|received?)\s+"
                r"(?:uang|dana|kas)?\s*"
                r"(?:Rp\.?|IDR)?\s*([\d.,]+)",
                re.IGNORECASE
            ),
            "add_expense": re.compile(
                r"(?:bayar|keluar|beli|expense|spent?|belanja)\s+"
                r"(?:uang|dana|kas)?\s*"
                r"(?:Rp\.?|IDR)?\s*([\d.,]+)",
                re.IGNORECASE
            ),
            "check_balance": re.compile(
                r"(?:berapa|cek|lihat|saldo|balance|kas|uang)",
                re.IGNORECASE
            ),
            "report_request": re.compile(
                r"(?:laporan|report|rekap|summary|rangkuman)",
                re.IGNORECASE
            ),
            "help_request": re.compile(
                r"(?:bantuan|help|cara|gimana|bagaimana|apa saja)",
                re.IGNORECASE
            )
        }

    async def route_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        is_group: bool = True,
        should_respond: bool = False,
        reply_to_message_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Route an incoming message and generate appropriate response.

        Args:
            chat_id: The chat ID
            user_id: The user's ID
            username: The user's username
            text: The message text
            is_group: Whether this is a group chat
            should_respond: Whether bot should respond
            reply_to_message_id: Message ID being replied to

        Returns:
            Response text or None if no response needed
        """
        logger.info(f"Routing message from {username} ({user_id}) in {chat_id}")

        intent, extracted_data = await self._detect_intent(text)
        logger.debug(f"Detected intent: {intent}, data: {extracted_data}")

        await self._store_message(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            text=text,
            intent=intent
        )

        if intent == "add_income" and extracted_data.get("amount"):
            return await self._handle_add_transaction(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                tx_type="income",
                amount=extracted_data["amount"],
                description=extracted_data.get("description", text)
            )

        if intent == "add_expense" and extracted_data.get("amount"):
            return await self._handle_add_transaction(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                tx_type="expense",
                amount=extracted_data["amount"],
                description=extracted_data.get("description", text)
            )

        if intent == "check_balance":
            return await self._handle_balance_check(chat_id)

        if intent == "report_request":
            return await self._handle_report_request(chat_id)

        if should_respond:
            return await self._generate_ai_response(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                text=text
            )

        return None

    async def route_private_message(
        self,
        user_id: int,
        username: str,
        text: str
    ) -> Optional[str]:
        """
        Route a private message.

        Private messages receive help and guidance about the bot.
        """
        intent, _ = await self._detect_intent(text)

        if intent == "help_request":
            return (
                "Halo! Saya adalah AI Finance Assistant untuk grup Telegram.\n\n"
                "<b>Cara Menggunakan:</b>\n"
                "1. Tambahkan saya ke grup Anda\n"
                "2. Jadikan saya admin grup\n"
                "3. Ketik /setup di grup untuk memulai\n\n"
                "Setelah setup, Anda bisa:\n"
                "• Mention saya untuk bertanya\n"
                "• Catat transaksi dengan bahasa natural\n"
                "• Lihat laporan keuangan\n\n"
                "Ketik /help untuk info lebih lanjut."
            )

        return (
            "Saya adalah bot untuk manajemen keuangan grup.\n"
            "Tambahkan saya ke grup Anda dan jalankan /setup untuk memulai.\n\n"
            "Ketik /help untuk bantuan."
        )

    async def route_admin_message(
        self,
        user_id: int,
        username: str,
        text: str
    ) -> Optional[str]:
        """
        Route a message from a super admin.
        """
        text_lower = text.lower()

        if "stats" in text_lower or "statistik" in text_lower:
            return await self._get_admin_stats()

        if "groups" in text_lower or "grup" in text_lower:
            return await self._get_groups_summary()

        return (
            "Halo Admin! Perintah yang tersedia:\n\n"
            "• 'stats' - Lihat statistik sistem\n"
            "• 'groups' - Daftar grup aktif\n"
            "• /admin - Panel admin lengkap\n"
        )

    async def _detect_intent(
        self,
        text: str
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Detect the intent of a message.

        Returns:
            Tuple of (intent_name, extracted_data)
        """
        extracted_data = {}

        for intent_name, pattern in self._intent_patterns.items():
            match = pattern.search(text)
            if match:
                if intent_name in ["add_income", "add_expense"]:
                    amount = extract_amount(match.group(1))
                    if amount:
                        extracted_data["amount"] = amount
                        extracted_data["description"] = text
                        return intent_name, extracted_data
                else:
                    return intent_name, extracted_data

        transaction_intent = detect_transaction_intent(text)
        if transaction_intent:
            return transaction_intent["type"], transaction_intent

        return None, {}

    async def _store_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        intent: Optional[str] = None
    ) -> None:
        """Store message in memory for context."""
        try:
            group_data = await self.master_sheet.get_group(chat_id)
            if not group_data:
                return

            spreadsheet_id = group_data.get("spreadsheet_id")
            if not spreadsheet_id:
                return

            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)
            await group_sheet.add_memory_entry(
                user_id=user_id,
                username=username,
                message=text,
                intent=intent,
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"Failed to store message: {e}")

    async def _handle_add_transaction(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        tx_type: str,
        amount: float,
        description: str
    ) -> str:
        """Handle adding a transaction from natural language."""
        try:
            group_data = await self.master_sheet.get_group(chat_id)
            if not group_data or group_data.get("status") != "active":
                return "Grup ini belum aktif. Jalankan /setup terlebih dahulu."

            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            transaction = await group_sheet.add_transaction(
                tx_type=tx_type,
                amount=amount,
                description=description,
                user_id=user_id,
                username=username
            )

            type_emoji = "📈" if tx_type == "income" else "📉"
            type_label = "Pemasukan" if tx_type == "income" else "Pengeluaran"

            return (
                f"{type_emoji} <b>Transaksi Tercatat</b>\n\n"
                f"Tipe: {type_label}\n"
                f"Jumlah: Rp {amount:,.0f}\n"
                f"Keterangan: {description[:50]}...\n"
                f"ID: #{transaction['id']}"
            )

        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            return "Gagal mencatat transaksi. Silakan coba lagi."

    async def _handle_balance_check(self, chat_id: int) -> str:
        """Handle balance check request."""
        try:
            group_data = await self.master_sheet.get_group(chat_id)
            if not group_data or group_data.get("status") != "active":
                return "Grup ini belum aktif. Jalankan /setup terlebih dahulu."

            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            balance_data = await group_sheet.get_balance()

            return (
                f"💰 <b>Saldo Grup</b>\n\n"
                f"Pemasukan: Rp {balance_data['total_income']:,.0f}\n"
                f"Pengeluaran: Rp {balance_data['total_expense']:,.0f}\n"
                f"━━━━━━━━━━━━\n"
                f"<b>Saldo: Rp {balance_data['balance']:,.0f}</b>"
            )

        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return "Gagal mengambil saldo. Silakan coba lagi."

    async def _handle_report_request(self, chat_id: int) -> str:
        """Handle report request."""
        try:
            group_data = await self.master_sheet.get_group(chat_id)
            if not group_data or group_data.get("status") != "active":
                return "Grup ini belum aktif. Jalankan /setup terlebih dahulu."

            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            start_date = datetime.now().replace(day=1)
            report_data = await group_sheet.get_report(start_date)

            return (
                f"📊 <b>Laporan Bulan Ini</b>\n\n"
                f"📈 Pemasukan: Rp {report_data['total_income']:,.0f}\n"
                f"   ({report_data['income_count']} transaksi)\n\n"
                f"📉 Pengeluaran: Rp {report_data['total_expense']:,.0f}\n"
                f"   ({report_data['expense_count']} transaksi)\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Saldo: Rp {report_data['balance']:,.0f}</b>\n\n"
                f"Ketik /report untuk laporan lengkap."
            )

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return "Gagal membuat laporan. Silakan coba lagi."

    async def _generate_ai_response(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str
    ) -> str:
        """Generate AI response using context."""
        try:
            context = await self.context_builder.build_context(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                current_message=text
            )

            response = await self.ai_engine.generate_response(
                user_message=text,
                system_prompt=context["system_prompt"],
                conversation_history=context["conversation_history"],
                context_data=context["context_data"]
            )

            return response

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return (
                "Maaf, saya mengalami kesulitan memproses permintaan Anda. "
                "Silakan coba lagi atau gunakan perintah /help."
            )

    async def _get_admin_stats(self) -> str:
        """Get admin statistics summary."""
        try:
            stats = await self.master_sheet.get_global_stats()
            return (
                f"<b>📊 Statistik Sistem</b>\n\n"
                f"Total Grup: {stats['total_groups']}\n"
                f"Grup Aktif: {stats['active_groups']}\n"
                f"Total Transaksi: {stats['total_transactions']}\n"
                f"Total Volume: Rp {stats['total_volume']:,.0f}"
            )
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return "Gagal mengambil statistik."

    async def _get_groups_summary(self) -> str:
        """Get groups summary for admin."""
        try:
            groups = await self.master_sheet.get_all_groups()
            summary = "<b>👥 Daftar Grup</b>\n\n"

            for i, group in enumerate(groups[:20], 1):
                status = "✅" if group["status"] == "active" else "⏳"
                summary += f"{i}. {status} {group['name']}\n"

            if len(groups) > 20:
                summary += f"\n... dan {len(groups) - 20} grup lainnya"

            return summary
        except Exception as e:
            logger.error(f"Error getting groups summary: {e}")
            return "Gagal mengambil daftar grup."
