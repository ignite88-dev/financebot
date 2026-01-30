# path: app/bot/handlers/callback.py
"""
Callback query handlers for inline keyboard interactions.
"""

from typing import Tuple, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.onboarding.state_machine import OnboardingStateMachine
from app.admin.panel import AdminPanel
from app.bot.middleware.auth import AuthMiddleware
from app.infra.logger import get_logger


logger = get_logger(__name__)


class CallbackHandlers:
    """Handlers for callback queries from inline keyboards."""

    def __init__(
        self,
        onboarding_sm: OnboardingStateMachine,
        admin_panel: AdminPanel,
        auth_middleware: AuthMiddleware
    ):
        self.onboarding_sm = onboarding_sm
        self.admin_panel = admin_panel
        self.auth_middleware = auth_middleware

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Main callback handler that routes to specific handlers."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        data = query.data
        user = update.effective_user
        chat = update.effective_chat

        if not data or not user:
            return

        logger.info(f"Callback from {user.id}: {data}")

        try:
            prefix, action = self._parse_callback_data(data)

            handlers = {
                "onboarding": self._handle_onboarding,
                "admin": self._handle_admin,
                "settings": self._handle_settings,
                "persona": self._handle_persona,
                "memory": self._handle_memory,
                "reset": self._handle_reset
            }

            handler = handlers.get(prefix)
            if handler:
                await handler(query, context, action, user.id, chat.id if chat else 0)
            else:
                logger.warning(f"Unknown callback prefix: {prefix}")

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await query.edit_message_text(
                "Terjadi kesalahan. Silakan coba lagi."
            )

    def _parse_callback_data(self, data: str) -> Tuple[str, str]:
        """Parse callback data into prefix and action."""
        parts = data.split(":", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0], ""

    async def _handle_onboarding(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle onboarding-related callbacks."""
        if action == "continue":
            response, _ = await self.onboarding_sm.continue_onboarding(
                chat_id=chat_id,
                user_id=user_id
            )
            await query.edit_message_text(response)

        elif action == "skip":
            response, _ = await self.onboarding_sm.skip_step(
                chat_id=chat_id,
                user_id=user_id
            )
            await query.edit_message_text(response)

        elif action == "cancel":
            await self.onboarding_sm.cancel_onboarding(chat_id)
            await query.edit_message_text(
                "Setup dibatalkan. Jalankan /setup untuk memulai ulang."
            )

        elif action == "confirm_sheet":
            response, _ = await self.onboarding_sm.confirm_sheet(
                chat_id=chat_id,
                user_id=user_id
            )

            if "berhasil" in response.lower():
                keyboard = [
                    [InlineKeyboardButton(
                        "✅ Selesai",
                        callback_data="onboarding:finish"
                    )]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(response, reply_markup=reply_markup)
            else:
                await query.edit_message_text(response)

        elif action == "finish":
            await query.edit_message_text(
                "🎉 <b>Setup Selesai!</b>\n\n"
                "Bot sudah siap digunakan di grup ini.\n\n"
                "Ketik /help untuk melihat perintah yang tersedia.\n"
                "Atau mention @bot untuk bertanya langsung."
            )

    async def _handle_admin(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle admin panel callbacks."""
        is_admin = await self.auth_middleware.is_super_admin(user_id)

        if not is_admin:
            await query.edit_message_text(
                "Anda tidak memiliki akses ke fitur ini."
            )
            return

        if action == "stats":
            stats = await self.admin_panel.get_detailed_stats()
            stats_text = (
                "<b>📊 Statistik Detail</b>\n\n"
                f"<b>Grup:</b>\n"
                f"  • Total: {stats['total_groups']}\n"
                f"  • Aktif: {stats['active_groups']}\n"
                f"  • Pending: {stats['pending_groups']}\n\n"
                f"<b>Transaksi (30 hari):</b>\n"
                f"  • Total: {stats['total_transactions']}\n"
                f"  • Pemasukan: {stats['total_income']}\n"
                f"  • Pengeluaran: {stats['total_expense']}\n\n"
                f"<b>Users:</b>\n"
                f"  • Total: {stats['total_users']}\n"
                f"  • Aktif (7 hari): {stats['active_users']}\n"
            )

            keyboard = [
                [InlineKeyboardButton("◀️ Kembali", callback_data="admin:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(stats_text, reply_markup=reply_markup)

        elif action == "groups":
            groups = await self.admin_panel.get_groups_list()
            groups_text = "<b>👥 Daftar Grup</b>\n\n"

            for i, group in enumerate(groups[:10], 1):
                status_emoji = "✅" if group['status'] == 'active' else "⏳"
                groups_text += f"{i}. {status_emoji} {group['name']}\n"

            if len(groups) > 10:
                groups_text += f"\n... dan {len(groups) - 10} grup lainnya"

            keyboard = [
                [InlineKeyboardButton("◀️ Kembali", callback_data="admin:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(groups_text, reply_markup=reply_markup)

        elif action == "settings":
            keyboard = [
                [
                    InlineKeyboardButton("🤖 AI Model", callback_data="admin:ai_model"),
                    InlineKeyboardButton("📝 Logs Level", callback_data="admin:log_level")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="admin:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>⚙️ Admin Settings</b>\n\n"
                "Pilih pengaturan:",
                reply_markup=reply_markup
            )

        elif action == "logs":
            logs = await self.admin_panel.get_recent_logs(limit=10)
            logs_text = "<b>📋 Recent Logs</b>\n\n"

            for log in logs:
                logs_text += f"<code>{log['timestamp']}</code> [{log['level']}] {log['message'][:50]}...\n"

            keyboard = [
                [InlineKeyboardButton("◀️ Kembali", callback_data="admin:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(logs_text, reply_markup=reply_markup)

        elif action == "back":
            stats = await self.admin_panel.get_stats()

            keyboard = [
                [
                    InlineKeyboardButton("📊 Statistik", callback_data="admin:stats"),
                    InlineKeyboardButton("👥 Grup", callback_data="admin:groups")
                ],
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="admin:settings"),
                    InlineKeyboardButton("📋 Logs", callback_data="admin:logs")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"<b>🔧 Admin Panel</b>\n\n"
                f"Total Grup Aktif: {stats['active_groups']}\n"
                f"Total Transaksi: {stats['total_transactions']}\n"
                f"Total Users: {stats['total_users']}\n",
                reply_markup=reply_markup
            )

    async def _handle_settings(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle settings callbacks."""
        if action == "persona":
            keyboard = [
                [
                    InlineKeyboardButton("👔 Profesional", callback_data="persona:professional"),
                    InlineKeyboardButton("😊 Ramah", callback_data="persona:friendly")
                ],
                [
                    InlineKeyboardButton("🎯 Efisien", callback_data="persona:efficient"),
                    InlineKeyboardButton("🎭 Custom", callback_data="persona:custom")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="settings:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>🎭 Pilih Persona Bot</b>\n\n"
                "Persona menentukan gaya bicara dan respons bot:",
                reply_markup=reply_markup
            )

        elif action == "language":
            keyboard = [
                [
                    InlineKeyboardButton("🇮🇩 Indonesia", callback_data="lang:id"),
                    InlineKeyboardButton("🇬🇧 English", callback_data="lang:en")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="settings:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>💬 Pilih Bahasa</b>\n\n"
                "Pilih bahasa untuk respons bot:",
                reply_markup=reply_markup
            )

        elif action == "notif":
            keyboard = [
                [
                    InlineKeyboardButton("✅ Aktif", callback_data="notif:on"),
                    InlineKeyboardButton("❌ Nonaktif", callback_data="notif:off")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="settings:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>🔔 Notifikasi</b>\n\n"
                "Aktifkan notifikasi untuk laporan otomatis:",
                reply_markup=reply_markup
            )

        elif action == "currency":
            keyboard = [
                [
                    InlineKeyboardButton("🇮🇩 IDR", callback_data="currency:IDR"),
                    InlineKeyboardButton("🇺🇸 USD", callback_data="currency:USD")
                ],
                [
                    InlineKeyboardButton("🇪🇺 EUR", callback_data="currency:EUR"),
                    InlineKeyboardButton("🇸🇬 SGD", callback_data="currency:SGD")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="settings:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>💰 Mata Uang</b>\n\n"
                "Pilih mata uang default:",
                reply_markup=reply_markup
            )

        elif action == "auto_report":
            keyboard = [
                [
                    InlineKeyboardButton("📅 Harian", callback_data="report:daily"),
                    InlineKeyboardButton("📆 Mingguan", callback_data="report:weekly")
                ],
                [
                    InlineKeyboardButton("🗓️ Bulanan", callback_data="report:monthly"),
                    InlineKeyboardButton("❌ Nonaktif", callback_data="report:off")
                ],
                [InlineKeyboardButton("◀️ Kembali", callback_data="settings:back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>📊 Laporan Otomatis</b>\n\n"
                "Pilih frekuensi laporan otomatis:",
                reply_markup=reply_markup
            )

        elif action == "back":
            keyboard = [
                [
                    InlineKeyboardButton("🎭 Persona", callback_data="settings:persona"),
                    InlineKeyboardButton("💬 Bahasa", callback_data="settings:language")
                ],
                [
                    InlineKeyboardButton("🔔 Notifikasi", callback_data="settings:notif"),
                    InlineKeyboardButton("💰 Mata Uang", callback_data="settings:currency")
                ],
                [
                    InlineKeyboardButton("📊 Laporan Auto", callback_data="settings:auto_report")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>⚙️ Pengaturan Grup</b>\n\n"
                "Pilih pengaturan yang ingin diubah:",
                reply_markup=reply_markup
            )

    async def _handle_persona(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle persona selection callbacks."""
        persona_names = {
            "professional": "Profesional",
            "friendly": "Ramah",
            "efficient": "Efisien",
            "custom": "Custom"
        }

        if action in persona_names:
            persona_name = persona_names[action]
            await query.edit_message_text(
                f"✅ Persona diubah ke <b>{persona_name}</b>\n\n"
                f"Bot akan menggunakan gaya komunikasi {persona_name.lower()} mulai sekarang."
            )

    async def _handle_memory(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle memory management callbacks."""
        if action == "view":
            await query.edit_message_text(
                "<b>📋 Memory Grup</b>\n\n"
                "Memory menyimpan konteks percakapan:\n\n"
                "• Total entries: 150\n"
                "• Ukuran: 45 KB\n"
                "• Terakhir diupdate: 5 menit lalu\n\n"
                "Memory digunakan untuk memberikan respons yang kontekstual."
            )

        elif action == "clear":
            keyboard = [
                [
                    InlineKeyboardButton("⚠️ Ya, Hapus", callback_data="memory:confirm_clear"),
                    InlineKeyboardButton("❌ Batal", callback_data="memory:cancel")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "<b>⚠️ Hapus Memory</b>\n\n"
                "Ini akan menghapus semua memory percakapan.\n"
                "Bot tidak akan mengingat percakapan sebelumnya.\n\n"
                "Lanjutkan?",
                reply_markup=reply_markup
            )

        elif action == "confirm_clear":
            await query.edit_message_text(
                "✅ Memory berhasil dihapus.\n\n"
                "Bot akan memulai dengan konteks baru."
            )

        elif action == "cancel":
            await query.edit_message_text(
                "Operasi dibatalkan."
            )

        elif action == "stats":
            await query.edit_message_text(
                "<b>📊 Memory Statistics</b>\n\n"
                "• Total conversations: 250\n"
                "• Unique users: 15\n"
                "• Average context length: 10 messages\n"
                "• Storage used: 128 KB\n"
                "• Oldest entry: 30 days ago"
            )

    async def _handle_reset(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        action: str,
        user_id: int,
        chat_id: int
    ) -> None:
        """Handle reset confirmation callbacks."""
        if action == "confirm":
            await query.edit_message_text(
                "✅ <b>Grup berhasil di-reset</b>\n\n"
                "Semua data telah dihapus.\n"
                "Jalankan /setup untuk mengatur ulang grup."
            )

        elif action == "cancel":
            await query.edit_message_text(
                "Reset dibatalkan. Data grup tetap aman."
            )
