# path: app/admin/commands.py
"""
Admin Commands - Admin-specific bot commands.
"""

from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.admin.panel import AdminPanel
from app.bot.middleware.auth import AuthMiddleware
from app.infra.logger import get_logger
from app.infra.utils import format_currency


logger = get_logger(__name__)


class AdminCommands:
    """
    Handles admin-specific commands.
    """

    def __init__(
        self,
        admin_panel: AdminPanel,
        auth_middleware: AuthMiddleware
    ):
        self.admin_panel = admin_panel
        self.auth_middleware = auth_middleware

    async def stats(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /adminstats command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        stats = await self.admin_panel.get_stats()

        stats_text = (
            "<b>📊 Statistik Sistem</b>\n\n"
            f"Total Grup: {stats['total_groups']}\n"
            f"Grup Aktif: {stats['active_groups']}\n"
            f"Total Transaksi: {stats['total_transactions']}\n"
            f"Total Users: {stats['total_users']}\n"
            f"Super Admins: {stats['super_admins']}\n\n"
            f"<i>Generated: {stats['generated_at']}</i>"
        )

        await message.reply_text(stats_text)

    async def groups(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /admingroups command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        status_filter = args[0] if args else None

        groups = await self.admin_panel.get_groups_list(
            status=status_filter,
            limit=20
        )

        if not groups:
            await message.reply_text("Tidak ada grup yang ditemukan.")
            return

        groups_text = "<b>👥 Daftar Grup</b>\n\n"

        for i, group in enumerate(groups, 1):
            status_emoji = "✅" if group["status"] == "active" else "⏸️"
            groups_text += (
                f"{i}. {status_emoji} <b>{group['chat_title']}</b>\n"
                f"   Admin: @{group['admin_username']}\n"
                f"   Transaksi: {group['transaction_count']}\n\n"
            )

        keyboard = [
            [
                InlineKeyboardButton("Active", callback_data="admin:groups:active"),
                InlineKeyboardButton("Suspended", callback_data="admin:groups:suspended")
            ],
            [
                InlineKeyboardButton("All", callback_data="admin:groups:all")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(groups_text, reply_markup=reply_markup)

    async def group_info(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /groupinfo <chat_id> command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        if not args:
            await message.reply_text(
                "Usage: /groupinfo <chat_id>"
            )
            return

        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("Chat ID harus berupa angka.")
            return

        details = await self.admin_panel.get_group_details(chat_id)

        if not details:
            await message.reply_text("Grup tidak ditemukan.")
            return

        info_text = (
            f"<b>📋 Info Grup</b>\n\n"
            f"<b>ID:</b> {details['chat_id']}\n"
            f"<b>Nama:</b> {details['chat_title']}\n"
            f"<b>Status:</b> {details['status']}\n"
            f"<b>Admin:</b> @{details['admin_username']}\n"
            f"<b>Members:</b> {details['member_count']}\n"
            f"<b>Transaksi:</b> {details['transaction_count']}\n"
            f"<b>Dibuat:</b> {details['created_at']}\n"
            f"<b>Terakhir Aktif:</b> {details['last_active']}\n\n"
            f"<b>Spreadsheet:</b>\n{details['spreadsheet_url']}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "⏸️ Suspend",
                    callback_data=f"admin:suspend:{chat_id}"
                ),
                InlineKeyboardButton(
                    "🗑️ Delete",
                    callback_data=f"admin:delete:{chat_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(info_text, reply_markup=reply_markup)

    async def suspend(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /suspend <chat_id> [reason] command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        if not args:
            await message.reply_text(
                "Usage: /suspend <chat_id> [reason]"
            )
            return

        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("Chat ID harus berupa angka.")
            return

        reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"

        success = await self.admin_panel.suspend_group(chat_id, reason)

        if success:
            await message.reply_text(
                f"✅ Grup {chat_id} telah di-suspend.\n"
                f"Alasan: {reason}"
            )
        else:
            await message.reply_text("❌ Gagal men-suspend grup.")

    async def reactivate(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /reactivate <chat_id> command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        if not args:
            await message.reply_text(
                "Usage: /reactivate <chat_id>"
            )
            return

        try:
            chat_id = int(args[0])
        except ValueError:
            await message.reply_text("Chat ID harus berupa angka.")
            return

        success = await self.admin_panel.reactivate_group(chat_id)

        if success:
            await message.reply_text(f"✅ Grup {chat_id} telah diaktifkan kembali.")
        else:
            await message.reply_text("❌ Gagal mengaktifkan grup.")

    async def logs(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /adminlogs command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        level_filter = args[0].upper() if args else None

        logs = await self.admin_panel.get_system_logs(
            limit=20,
            level=level_filter
        )

        if not logs:
            await message.reply_text("Tidak ada log yang ditemukan.")
            return

        logs_text = "<b>📋 System Logs</b>\n\n"

        for log in logs[:15]:
            level_emoji = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌"
            }.get(log["level"], "📝")

            logs_text += (
                f"{level_emoji} <code>{log['timestamp'][:19]}</code>\n"
                f"   {log['message'][:50]}\n\n"
            )

        await message.reply_text(logs_text)

    async def settings(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /adminsettings command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        settings = await self.admin_panel.get_global_settings()

        settings_text = "<b>⚙️ Global Settings</b>\n\n"

        for key, value in settings.items():
            settings_text += f"<b>{key}:</b> {value}\n"

        keyboard = [
            [InlineKeyboardButton(
                "✏️ Edit Setting",
                callback_data="admin:settings:edit"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(settings_text, reply_markup=reply_markup)

    async def add_admin(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /addadmin <user_id> <username> command."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        if not args or len(args) < 2:
            await message.reply_text(
                "Usage: /addadmin <user_id> <username>"
            )
            return

        try:
            new_admin_id = int(args[0])
        except ValueError:
            await message.reply_text("User ID harus berupa angka.")
            return

        new_admin_username = args[1].lstrip("@")

        success = await self.admin_panel.add_super_admin(
            user_id=new_admin_id,
            username=new_admin_username,
            added_by=user.username or str(user.id)
        )

        if success:
            await message.reply_text(
                f"✅ Super admin baru ditambahkan:\n"
                f"ID: {new_admin_id}\n"
                f"Username: @{new_admin_username}"
            )
        else:
            await message.reply_text("❌ Gagal menambahkan super admin.")

    async def inactive(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /inactive [days] command - Show inactive groups."""
        user = update.effective_user
        message = update.effective_message

        if not user or not message:
            return

        is_admin = await self.auth_middleware.is_super_admin(user.id)
        if not is_admin:
            await message.reply_text(
                "Anda tidak memiliki akses ke perintah ini."
            )
            return

        args = context.args
        days = int(args[0]) if args else 30

        inactive_groups = await self.admin_panel.get_inactive_groups(days=days)

        if not inactive_groups:
            await message.reply_text(
                f"Tidak ada grup yang tidak aktif selama {days} hari terakhir."
            )
            return

        text = f"<b>💤 Grup Tidak Aktif ({days}+ hari)</b>\n\n"

        for group in inactive_groups[:20]:
            text += (
                f"• <b>{group['chat_title']}</b>\n"
                f"  Tidak aktif: {group['inactive_days']} hari\n\n"
            )

        await message.reply_text(text)
