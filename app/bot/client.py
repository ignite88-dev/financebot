# path: app/bot/client.py
"""
Telegram Bot Client - Main bot class that handles all bot operations.
"""

from typing import Optional, Dict, Any
from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    Defaults
)

from app.config.settings import Settings
from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.memory.manager import MemoryManager
from app.persona.loader import PersonaLoader
from app.bot.handlers.message import MessageHandlers
from app.bot.handlers.command import CommandHandlers
from app.bot.handlers.callback import CallbackHandlers
from app.bot.handlers.error import error_handler
from app.bot.middleware.auth import AuthMiddleware
from app.bot.middleware.logging import LoggingMiddleware
from app.core.router import MessageRouter
from app.core.context import ContextBuilder
from app.core.ai_engine import AIEngine
from app.onboarding.state_machine import OnboardingStateMachine
from app.admin.panel import AdminPanel
from app.infra.logger import get_logger


logger = get_logger(__name__)


class BotClient:
    """
    Main Telegram bot client that orchestrates all bot operations.
    """

    def __init__(
        self,
        token: str,
        sheets_client: SheetsClient,
        master_sheet: MasterSheet,
        memory_manager: MemoryManager,
        persona_loader: PersonaLoader,
        settings: Settings
    ):
        self.token = token
        self.sheets_client = sheets_client
        self.master_sheet = master_sheet
        self.memory_manager = memory_manager
        self.persona_loader = persona_loader
        self.settings = settings

        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None

        self.ai_engine: Optional[AIEngine] = None
        self.context_builder: Optional[ContextBuilder] = None
        self.message_router: Optional[MessageRouter] = None
        self.onboarding_sm: Optional[OnboardingStateMachine] = None
        self.admin_panel: Optional[AdminPanel] = None

        self.auth_middleware: Optional[AuthMiddleware] = None
        self.logging_middleware: Optional[LoggingMiddleware] = None

        self.message_handlers: Optional[MessageHandlers] = None
        self.command_handlers: Optional[CommandHandlers] = None
        self.callback_handlers: Optional[CallbackHandlers] = None

    async def initialize(self) -> None:
        """Initialize the bot client and all its components."""
        logger.info("Initializing bot client...")

        self.ai_engine = AIEngine(
            api_key=self.settings.openai_api_key,
            model=self.settings.ai_model,
            max_tokens=self.settings.ai_max_tokens
        )

        self.context_builder = ContextBuilder(
            sheets_client=self.sheets_client,
            memory_manager=self.memory_manager,
            persona_loader=self.persona_loader
        )

        self.message_router = MessageRouter(
            ai_engine=self.ai_engine,
            context_builder=self.context_builder,
            sheets_client=self.sheets_client,
            master_sheet=self.master_sheet
        )

        self.onboarding_sm = OnboardingStateMachine(
            sheets_client=self.sheets_client,
            master_sheet=self.master_sheet
        )

        self.admin_panel = AdminPanel(
            sheets_client=self.sheets_client,
            master_sheet=self.master_sheet
        )

        self.auth_middleware = AuthMiddleware(
            master_sheet=self.master_sheet
        )

        self.logging_middleware = LoggingMiddleware()

        self.message_handlers = MessageHandlers(
            router=self.message_router,
            onboarding_sm=self.onboarding_sm,
            auth_middleware=self.auth_middleware,
            master_sheet=self.master_sheet
        )

        self.command_handlers = CommandHandlers(
            router=self.message_router,
            onboarding_sm=self.onboarding_sm,
            admin_panel=self.admin_panel,
            auth_middleware=self.auth_middleware,
            master_sheet=self.master_sheet,
            sheets_client=self.sheets_client
        )

        self.callback_handlers = CallbackHandlers(
            onboarding_sm=self.onboarding_sm,
            admin_panel=self.admin_panel,
            auth_middleware=self.auth_middleware
        )

        defaults = Defaults(
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .defaults(defaults)
            .build()
        )

        self.bot = self.application.bot

        self._register_handlers()

        logger.info("Bot client initialized successfully")

    def _register_handlers(self) -> None:
        """Register all command, message, and callback handlers."""
        logger.info("Registering handlers...")

        self.application.add_handler(
            CommandHandler("start", self.command_handlers.start)
        )
        self.application.add_handler(
            CommandHandler("help", self.command_handlers.help)
        )
        self.application.add_handler(
            CommandHandler("setup", self.command_handlers.setup)
        )
        self.application.add_handler(
            CommandHandler("status", self.command_handlers.status)
        )
        self.application.add_handler(
            CommandHandler("balance", self.command_handlers.balance)
        )
        self.application.add_handler(
            CommandHandler("add", self.command_handlers.add_transaction)
        )
        self.application.add_handler(
            CommandHandler("report", self.command_handlers.report)
        )
        self.application.add_handler(
            CommandHandler("export", self.command_handlers.export)
        )
        self.application.add_handler(
            CommandHandler("admin", self.command_handlers.admin)
        )
        self.application.add_handler(
            CommandHandler("settings", self.command_handlers.settings)
        )
        self.application.add_handler(
            CommandHandler("persona", self.command_handlers.persona)
        )
        self.application.add_handler(
            CommandHandler("memory", self.command_handlers.memory)
        )
        self.application.add_handler(
            CommandHandler("reset", self.command_handlers.reset)
        )

        self.application.add_handler(
            CallbackQueryHandler(self.callback_handlers.handle)
        )

        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                self.message_handlers.handle_group_message
            )
        )

        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                self.message_handlers.handle_private_message
            )
        )

        self.application.add_error_handler(error_handler)

        logger.info("All handlers registered")

    async def start(self) -> None:
        """Start the bot polling."""
        logger.info("Starting bot...")

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

        logger.info("Bot started successfully")

    async def stop(self) -> None:
        """Stop the bot."""
        logger.info("Stopping bot...")

        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        logger.info("Bot stopped")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs
    ) -> None:
        """Send a message to a chat."""
        await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)

    async def get_bot_info(self) -> Dict[str, Any]:
        """Get bot information."""
        me = await self.bot.get_me()
        return {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "can_join_groups": me.can_join_groups,
            "can_read_all_group_messages": me.can_read_all_group_messages
        }
