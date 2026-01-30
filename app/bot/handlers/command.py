# path: app/bot/handlers/command.py
"""
Command handlers for all bot commands.
"""

from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta

from app.core.router import MessageRouter
from app.onboarding.state_machine import OnboardingStateMachine
from app.onboarding.states import OnboardingState
from app.admin.panel import AdminPanel
from app.bot.middleware.auth import AuthMiddleware
from app.sheets.master import MasterSheet
from app.sheets.client import SheetsClient
from app.sheets.group import GroupSheet
from app.infra.logger import get_logger
from app.infra.utils import format_currency, format_date
from app.config.constants import (
    HELP_TEXT,
    WELCOME_TEXT,
    SETUP_INSTRUCTIONS,
    ADMIN_HELP_TEXT
)


logger = get_logger(__name__)


class CommandHandlers:
    """Handlers for all bot commands."""

    def __init__(
        self,
        router: MessageRouter,
        onboarding_sm: OnboardingStateMachine,
        admin_panel: AdminPanel,
        auth_middleware: AuthMiddleware,
        master_sheet: MasterSheet,
        sheets_client: SheetsClient
    ):
        self.router = router
        self.onboarding_sm = onboarding_sm
        self.admin_panel = admin_panel
        self.auth_middleware = auth_middleware
        self.master_sheet = master_sheet
        self.sheets_client = sheets_client

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/start from {user.id} in chat {chat.id}")

        if chat.type == "private":
            welcome_text = (
                f"Halo {user.first_name}! 👋\n\n"
                f"Saya adalah <b>AI Finance Assistant</b> untuk grup Telegram.\n\n"
                f"<b>Cara Menggunakan:</b>\n"
                f"1. Tambahkan saya ke grup Anda\n"
                f"2. Jadikan saya admin grup\n"
                f"3. Ketik /setup di grup untuk memulai\n\n"
                f"Ketik /help untuk melihat semua perintah."
            )
            await message.reply_text(welcome_text)
        else:
            group_data = await self.master_sheet.get_group(chat.id)

            if group_data and group_data.get("status") == "active":
                await message.reply_text(
                    f"Grup ini sudah terdaftar dan aktif! ✅\n"
                    f"Ketik /help untuk melihat perintah yang tersedia."
                )
            else:
                await message.reply_text(WELCOME_TEXT)

    async def help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/help from {user.id}")

        is_admin = await self.auth_middleware.is_super_admin(user.id)

        if is_admin and chat.type == "private":
            help_text = ADMIN_HELP_TEXT
        else:
            help_text = HELP_TEXT

        await message.reply_text(help_text)

    async def setup(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /setup command - Start onboarding process."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/setup from {user.id} in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah /setup hanya bisa digunakan di grup.\n"
                "Silakan tambahkan saya ke grup dan jalankan /setup di sana."
            )
            return

        is_admin = await self._is_chat_admin(update, context, user.id)
        if not is_admin:
            await message.reply_text(
                "Hanya admin grup yang bisa menjalankan setup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)
        if group_data and group_data.get("status") == "active":
            await message.reply_text(
                "Grup ini sudah aktif! ✅\n"
                "Gunakan /reset jika ingin mengatur ulang."
            )
            return

        await self.onboarding_sm.start_onboarding(
            chat_id=chat.id,
            chat_title=chat.title or "Unknown Group",
            admin_user_id=user.id,
            admin_username=user.username or user.first_name
        )

        keyboard = [
            [InlineKeyboardButton(
                "📋 Lanjutkan Setup",
                callback_data="onboarding:continue"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(SETUP_INSTRUCTIONS, reply_markup=reply_markup)

    async def status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command - Show group status."""
        chat = update.effective_chat
        message = update.effective_message

        if not chat or not message:
            return

        logger.info(f"/status in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data:
            await message.reply_text(
                "Grup ini belum terdaftar.\n"
                "Jalankan /setup untuk memulai."
            )
            return

        status = group_data.get("status", "unknown")
        sheet_url = group_data.get("spreadsheet_url", "-")
        created_at = group_data.get("created_at", "-")
        admin_name = group_data.get("admin_username", "-")

        status_emoji = "✅" if status == "active" else "⏳"

        status_text = (
            f"<b>📊 Status Grup</b>\n\n"
            f"Status: {status_emoji} {status.upper()}\n"
            f"Admin: @{admin_name}\n"
            f"Dibuat: {created_at}\n"
            f"Spreadsheet: {sheet_url}\n"
        )

        await message.reply_text(status_text)

    async def balance(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /balance command - Show current balance."""
        chat = update.effective_chat
        message = update.effective_message

        if not chat or not message:
            return

        logger.info(f"/balance in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

        try:
            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            balance_data = await group_sheet.get_balance()

            balance_text = (
                f"<b>💰 Saldo Grup</b>\n\n"
                f"Total Pemasukan: {format_currency(balance_data['total_income'])}\n"
                f"Total Pengeluaran: {format_currency(balance_data['total_expense'])}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"<b>Saldo: {format_currency(balance_data['balance'])}</b>\n\n"
                f"📅 Per tanggal: {format_date(datetime.now())}"
            )

            await message.reply_text(balance_text)

        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            await message.reply_text(
                "Gagal mengambil data saldo. Silakan coba lagi."
            )

    async def add_transaction(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /add command - Add a transaction."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/add from {user.id} in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

        args = context.args
        if not args or len(args) < 2:
            await message.reply_text(
                "<b>Format:</b> /add [tipe] [jumlah] [keterangan]\n\n"
                "<b>Contoh:</b>\n"
                "/add masuk 1000000 Iuran bulanan\n"
                "/add keluar 500000 Beli peralatan\n\n"
                "<b>Tipe:</b> masuk, keluar, income, expense, in, out"
            )
            return

        try:
            tx_type_raw = args[0].lower()
            amount_str = args[1].replace(".", "").replace(",", "")
            description = " ".join(args[2:]) if len(args) > 2 else "Tidak ada keterangan"

            type_mapping = {
                "masuk": "income",
                "keluar": "expense",
                "income": "income",
                "expense": "expense",
                "in": "income",
                "out": "expense",
                "pemasukan": "income",
                "pengeluaran": "expense"
            }

            tx_type = type_mapping.get(tx_type_raw)
            if not tx_type:
                await message.reply_text(
                    f"Tipe transaksi '{tx_type_raw}' tidak valid.\n"
                    "Gunakan: masuk/keluar atau income/expense"
                )
                return

            amount = float(amount_str)
            if amount <= 0:
                await message.reply_text("Jumlah harus lebih dari 0.")
                return

            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            transaction = await group_sheet.add_transaction(
                tx_type=tx_type,
                amount=amount,
                description=description,
                user_id=user.id,
                username=user.username or user.first_name
            )

            type_emoji = "📈" if tx_type == "income" else "📉"
            type_label = "Pemasukan" if tx_type == "income" else "Pengeluaran"

            await message.reply_text(
                f"{type_emoji} <b>Transaksi Berhasil</b>\n\n"
                f"Tipe: {type_label}\n"
                f"Jumlah: {format_currency(amount)}\n"
                f"Keterangan: {description}\n"
                f"ID: #{transaction['id']}\n"
                f"Oleh: @{user.username or user.first_name}"
            )

        except ValueError:
            await message.reply_text(
                "Format jumlah tidak valid. Gunakan angka saja.\n"
                "Contoh: /add masuk 1000000 Iuran"
            )
        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            await message.reply_text(
                "Gagal menambah transaksi. Silakan coba lagi."
            )

    async def report(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /report command - Generate financial report."""
        chat = update.effective_chat
        message = update.effective_message

        if not chat or not message:
            return

        logger.info(f"/report in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

        args = context.args
        period = args[0] if args else "month"

        try:
            spreadsheet_id = group_data.get("spreadsheet_id")
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            if period == "week":
                start_date = datetime.now() - timedelta(days=7)
                period_label = "Minggu Ini"
            elif period == "month":
                start_date = datetime.now().replace(day=1)
                period_label = "Bulan Ini"
            elif period == "year":
                start_date = datetime.now().replace(month=1, day=1)
                period_label = "Tahun Ini"
            else:
                start_date = datetime.now() - timedelta(days=30)
                period_label = "30 Hari Terakhir"

            report_data = await group_sheet.get_report(start_date)

            report_text = (
                f"<b>📊 Laporan Keuangan - {period_label}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 <b>Pemasukan</b>\n"
                f"   Total: {format_currency(report_data['total_income'])}\n"
                f"   Jumlah Transaksi: {report_data['income_count']}\n\n"
                f"📉 <b>Pengeluaran</b>\n"
                f"   Total: {format_currency(report_data['total_expense'])}\n"
                f"   Jumlah Transaksi: {report_data['expense_count']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Saldo Akhir: {format_currency(report_data['balance'])}</b>\n\n"
                f"📅 Periode: {format_date(start_date)} - {format_date(datetime.now())}"
            )

            if report_data.get("top_expenses"):
                report_text += "\n\n<b>Top 5 Pengeluaran:</b>\n"
                for i, exp in enumerate(report_data["top_expenses"][:5], 1):
                    report_text += f"{i}. {exp['description']}: {format_currency(exp['amount'])}\n"

            await message.reply_text(report_text)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            await message.reply_text(
                "Gagal membuat laporan. Silakan coba lagi."
            )

    async def export(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /export command - Export data to spreadsheet."""
        chat = update.effective_chat
        message = update.effective_message

        if not chat or not message:
            return

        logger.info(f"/export in chat {chat.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

        spreadsheet_url = group_data.get("spreadsheet_url", "")

        await message.reply_text(
            f"<b>📤 Export Data</b>\n\n"
            f"Semua data grup sudah tersimpan di Google Sheets:\n"
            f"{spreadsheet_url}\n\n"
            f"Anda dapat mengakses spreadsheet untuk melihat atau mengunduh data."
        )

    async def admin(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /admin command - Admin panel."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/admin from {user.id}")

        is_super_admin = await self.auth_middleware.is_super_admin(user.id)

        if not is_super_admin:
            if chat.type != "private":
                is_group_admin = await self._is_chat_admin(update, context, user.id)
                if not is_group_admin:
                    await message.reply_text(
                        "Anda tidak memiliki akses ke panel admin."
                    )
                    return

        admin_stats = await self.admin_panel.get_stats()

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

        await message.reply_text(
            f"<b>🔧 Admin Panel</b>\n\n"
            f"Total Grup Aktif: {admin_stats['active_groups']}\n"
            f"Total Transaksi: {admin_stats['total_transactions']}\n"
            f"Total Users: {admin_stats['total_users']}\n",
            reply_markup=reply_markup
        )

    async def settings(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /settings command - Group settings."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/settings from {user.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        is_admin = await self._is_chat_admin(update, context, user.id)
        if not is_admin:
            await message.reply_text(
                "Hanya admin grup yang bisa mengubah settings."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

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

        await message.reply_text(
            "<b>⚙️ Pengaturan Grup</b>\n\n"
            "Pilih pengaturan yang ingin diubah:",
            reply_markup=reply_markup
        )

    async def persona(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /persona command - Change bot persona."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/persona from {user.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        is_admin = await self._is_chat_admin(update, context, user.id)
        if not is_admin:
            await message.reply_text(
                "Hanya admin grup yang bisa mengubah persona."
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("👔 Profesional", callback_data="persona:professional"),
                InlineKeyboardButton("😊 Ramah", callback_data="persona:friendly")
            ],
            [
                InlineKeyboardButton("🎯 Efisien", callback_data="persona:efficient"),
                InlineKeyboardButton("🎭 Custom", callback_data="persona:custom")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            "<b>🎭 Pilih Persona Bot</b>\n\n"
            "Persona menentukan gaya bicara dan respons bot:\n\n"
            "👔 <b>Profesional</b> - Formal dan bisnis\n"
            "😊 <b>Ramah</b> - Casual dan friendly\n"
            "🎯 <b>Efisien</b> - Singkat dan to the point\n"
            "🎭 <b>Custom</b> - Buat persona sendiri",
            reply_markup=reply_markup
        )

    async def memory(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /memory command - View/manage bot memory."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/memory from {user.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        is_admin = await self._is_chat_admin(update, context, user.id)
        if not is_admin:
            await message.reply_text(
                "Hanya admin grup yang bisa melihat memory."
            )
            return

        group_data = await self.master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await message.reply_text(
                "Grup ini belum aktif. Jalankan /setup terlebih dahulu."
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("📋 Lihat Memory", callback_data="memory:view"),
                InlineKeyboardButton("🗑️ Hapus", callback_data="memory:clear")
            ],
            [
                InlineKeyboardButton("📊 Stats", callback_data="memory:stats")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            "<b>🧠 Memory Management</b>\n\n"
            "Bot menyimpan konteks percakapan untuk memberikan respons yang lebih baik.\n\n"
            "Pilih aksi:",
            reply_markup=reply_markup
        )

    async def reset(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /reset command - Reset group setup."""
        chat = update.effective_chat
        user = update.effective_user
        message = update.effective_message

        if not chat or not user or not message:
            return

        logger.info(f"/reset from {user.id}")

        if chat.type == "private":
            await message.reply_text(
                "Perintah ini hanya tersedia di grup."
            )
            return

        is_admin = await self._is_chat_admin(update, context, user.id)
        if not is_admin:
            await message.reply_text(
                "Hanya admin grup yang bisa reset grup."
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("⚠️ Ya, Reset", callback_data="reset:confirm"),
                InlineKeyboardButton("❌ Batal", callback_data="reset:cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            "<b>⚠️ Reset Grup</b>\n\n"
            "Ini akan menghapus semua data dan pengaturan grup.\n"
            "Anda harus menjalankan /setup ulang.\n\n"
            "<b>Data yang akan dihapus:</b>\n"
            "- Semua transaksi\n"
            "- Memory percakapan\n"
            "- Pengaturan grup\n\n"
            "Apakah Anda yakin?",
            reply_markup=reply_markup
        )

    async def _is_chat_admin(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user_id: int
    ) -> bool:
        """Check if user is a chat administrator."""
        try:
            chat = update.effective_chat
            member = await context.bot.get_chat_member(chat.id, user_id)
            return member.status in ["creator", "administrator"]
        except Exception:
            return False
