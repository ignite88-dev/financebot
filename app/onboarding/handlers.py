# path: app/onboarding/handlers.py
"""
Onboarding Handlers - Handle onboarding-related callbacks and messages.
"""

from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.onboarding.state_machine import OnboardingStateMachine
from app.onboarding.states import OnboardingState, get_state_message
from app.infra.logger import get_logger


logger = get_logger(__name__)


class OnboardingHandlers:
    """
    Handlers for onboarding callbacks and messages.
    """

    def __init__(self, state_machine: OnboardingStateMachine):
        self.state_machine = state_machine

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        action: str
    ) -> None:
        """
        Handle onboarding callback queries.

        Args:
            update: The update object
            context: The context object
            action: The callback action
        """
        query = update.callback_query
        chat = update.effective_chat
        user = update.effective_user

        if not query or not chat or not user:
            return

        await query.answer()

        logger.info(f"Onboarding callback: {action} from {user.id} in {chat.id}")

        if action == "continue":
            await self._handle_continue(update, context)

        elif action == "create_new":
            await self._handle_create_new(update, context)

        elif action == "use_existing":
            await self._handle_use_existing(update, context)

        elif action == "retry":
            await self._handle_retry(update, context)

        elif action == "cancel":
            await self._handle_cancel(update, context)

        elif action == "view_sheet":
            await self._handle_view_sheet(update, context)

    async def handle_spreadsheet_url(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        url: str
    ) -> bool:
        """
        Handle a spreadsheet URL message during onboarding.

        Args:
            update: The update object
            context: The context object
            url: The spreadsheet URL

        Returns:
            True if handled
        """
        chat = update.effective_chat
        message = update.effective_message

        if not chat or not message:
            return False

        state_data = await self.state_machine.get_state(chat.id)
        if not state_data:
            return False

        if state_data.current_state != OnboardingState.SHARE_SHEET:
            return False

        logger.info(f"Processing spreadsheet URL for chat {chat.id}")

        processing_msg = await message.reply_text(
            "⏳ Memproses spreadsheet URL..."
        )

        state_data = await self.state_machine.process_spreadsheet_url(
            chat.id,
            url
        )

        if state_data.error:
            await processing_msg.edit_text(
                f"❌ {state_data.error}\n\n"
                "Silakan kirim URL yang valid atau buat spreadsheet baru."
            )
            return True

        state_data = await self.state_machine.complete_onboarding(chat.id)

        if state_data.is_complete():
            await processing_msg.edit_text(
                self._format_completion_message(state_data)
            )
        elif state_data.has_error():
            await processing_msg.edit_text(
                f"❌ Error: {state_data.error}\n\n"
                "Silakan coba lagi dengan /setup"
            )
        else:
            await processing_msg.edit_text(
                f"⏳ Status: {state_data.current_state.value}"
            )

        return True

    async def _handle_continue(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle continue button."""
        query = update.callback_query
        chat = update.effective_chat

        state_data = await self.state_machine.get_state(chat.id)
        if not state_data:
            await query.edit_message_text(
                "Sesi onboarding tidak ditemukan. Jalankan /setup untuk memulai."
            )
            return

        state_data = await self.state_machine.advance_state(chat.id)

        msg_config = get_state_message(state_data.current_state)

        keyboard = []
        for btn in msg_config.get("buttons", []):
            keyboard.append([
                InlineKeyboardButton(btn["text"], callback_data=btn["callback"])
            ])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        await query.edit_message_text(
            msg_config["message"],
            reply_markup=reply_markup
        )

    async def _handle_create_new(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle create new spreadsheet button."""
        query = update.callback_query
        chat = update.effective_chat

        await query.edit_message_text("⏳ Membuat spreadsheet baru...")

        state_data = await self.state_machine.create_new_spreadsheet(chat.id)

        if state_data.error:
            await query.edit_message_text(
                f"❌ Gagal membuat spreadsheet: {state_data.error}\n\n"
                "Silakan coba lagi."
            )
            return

        state_data = await self.state_machine.complete_onboarding(chat.id)

        if state_data.is_complete():
            await query.edit_message_text(
                self._format_completion_message(state_data)
            )
        else:
            await query.edit_message_text(
                f"❌ Error: {state_data.error or 'Unknown error'}"
            )

    async def _handle_use_existing(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle use existing spreadsheet button."""
        query = update.callback_query

        service_email = context.bot_data.get(
            "service_account_email",
            "bot-service-account@example.iam.gserviceaccount.com"
        )

        await query.edit_message_text(
            "<b>Menggunakan Spreadsheet Existing</b>\n\n"
            "1. Buka Google Spreadsheet Anda\n"
            "2. Klik tombol 'Share' di kanan atas\n"
            f"3. Tambahkan email ini sebagai Editor:\n"
            f"   <code>{service_email}</code>\n"
            "4. Kirim link spreadsheet ke chat ini\n\n"
            "Contoh link:\n"
            "<code>https://docs.google.com/spreadsheets/d/...</code>"
        )

    async def _handle_retry(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle retry button."""
        query = update.callback_query
        chat = update.effective_chat
        user = update.effective_user

        await self.state_machine.cancel_onboarding(chat.id)

        await self.state_machine.start_onboarding(
            chat_id=chat.id,
            chat_title=chat.title or "Unknown Group",
            admin_user_id=user.id,
            admin_username=user.username or user.first_name
        )

        msg_config = get_state_message(OnboardingState.WELCOME)

        keyboard = []
        for btn in msg_config.get("buttons", []):
            keyboard.append([
                InlineKeyboardButton(btn["text"], callback_data=btn["callback"])
            ])

        await query.edit_message_text(
            msg_config["message"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _handle_cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle cancel button."""
        query = update.callback_query
        chat = update.effective_chat

        await self.state_machine.cancel_onboarding(chat.id)

        await query.edit_message_text(
            "Setup dibatalkan.\n\n"
            "Jalankan /setup kapan saja untuk memulai lagi."
        )

    async def _handle_view_sheet(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle view spreadsheet button."""
        query = update.callback_query
        chat = update.effective_chat

        state_data = await self.state_machine.get_state(chat.id)

        if state_data and state_data.spreadsheet_url:
            await query.answer()
            await query.message.reply_text(
                f"📊 Spreadsheet grup:\n{state_data.spreadsheet_url}"
            )
        else:
            await query.answer("Spreadsheet tidak ditemukan", show_alert=True)

    def _format_completion_message(self, state_data) -> str:
        """Format the completion message."""
        return (
            "✅ <b>Setup Selesai!</b>\n\n"
            f"Grup <b>{state_data.chat_title}</b> sudah siap.\n\n"
            f"📊 Spreadsheet:\n{state_data.spreadsheet_url}\n\n"
            "<b>Perintah yang tersedia:</b>\n"
            "• /balance - Cek saldo\n"
            "• /add - Tambah transaksi\n"
            "• /report - Laporan keuangan\n"
            "• /help - Bantuan lengkap\n\n"
            "Selamat menggunakan! 🎉"
        )

    async def is_onboarding_message(
        self,
        chat_id: int,
        text: str
    ) -> bool:
        """
        Check if a message is relevant to onboarding.

        Args:
            chat_id: The chat ID
            text: The message text

        Returns:
            True if the message should be handled by onboarding
        """
        state_data = await self.state_machine.get_state(chat_id)
        if not state_data or not state_data.is_active():
            return False

        if state_data.current_state == OnboardingState.SHARE_SHEET:
            if "docs.google.com/spreadsheets" in text or "spreadsheets/d/" in text:
                return True

        return False
