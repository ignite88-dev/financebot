# path: app/main.py
"""
Main entry point for the Telegram AI Group Finance Assistant.
"""

import asyncio
import signal
import sys
from typing import Optional

from app.bot.client import BotClient
from app.config.settings import get_settings
from app.config.env import load_environment
from app.infra.logger import setup_logger, get_logger
from app.infra.exceptions import StartupError
from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.memory.manager import MemoryManager
from app.persona.loader import PersonaLoader


logger = get_logger(__name__)


class Application:
    """Main application class that orchestrates all components."""

    def __init__(self):
        self.settings = get_settings()
        self.bot_client: Optional[BotClient] = None
        self.sheets_client: Optional[SheetsClient] = None
        self.master_sheet: Optional[MasterSheet] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.persona_loader: Optional[PersonaLoader] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize all application components."""
        logger.info("Initializing application components...")

        try:
            self.sheets_client = SheetsClient(
                credentials_path=self.settings.google_credentials_path,
                service_account_email=self.settings.service_account_email
            )
            await self.sheets_client.initialize()
            logger.info("Sheets client initialized")

            self.master_sheet = MasterSheet(
                sheets_client=self.sheets_client,
                spreadsheet_id=self.settings.master_sheet_id
            )
            await self.master_sheet.initialize()
            logger.info("Master sheet initialized")

            self.memory_manager = MemoryManager(
                sheets_client=self.sheets_client
            )
            logger.info("Memory manager initialized")

            self.persona_loader = PersonaLoader(
                sheets_client=self.sheets_client
            )
            logger.info("Persona loader initialized")

            self.bot_client = BotClient(
                token=self.settings.telegram_token,
                sheets_client=self.sheets_client,
                master_sheet=self.master_sheet,
                memory_manager=self.memory_manager,
                persona_loader=self.persona_loader,
                settings=self.settings
            )
            await self.bot_client.initialize()
            logger.info("Bot client initialized")

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise StartupError(f"Application initialization failed: {e}")

    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting Telegram AI Group Finance Assistant...")

        await self.initialize()

        self._setup_signal_handlers()

        try:
            await self.bot_client.start()
            logger.info("Bot is running. Press Ctrl+C to stop.")
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error(f"Error during bot operation: {e}")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shutdown the application."""
        logger.info("Shutting down application...")

        if self.bot_client:
            await self.bot_client.stop()
            logger.info("Bot client stopped")

        if self.sheets_client:
            await self.sheets_client.close()
            logger.info("Sheets client closed")

        logger.info("Application shutdown complete")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._handle_shutdown())
            )

    async def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("Received shutdown signal")
        self._shutdown_event.set()


async def main() -> None:
    """Main entry point."""
    load_environment()
    setup_logger()

    app = Application()

    try:
        await app.start()
    except StartupError as e:
        logger.error(f"Startup failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
