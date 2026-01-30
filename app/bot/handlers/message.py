# path: app/bot/handlers/message.py
"""
Message handlers for processing incoming text messages.
"""

from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from app.core.router import MessageRouter
from app.onboarding.state_machine import OnboardingStateMachine
from app.onboarding.states import OnboardingState
from app.bot.middleware.auth import AuthMiddleware
from app.sheets.master import MasterSheet
from app.infra.logger import get_logger
from app.infra.exceptions import GroupNotFoundError, ProcessingError


logger = get_logger(__name__)


class MessageHandlers:
    """Handlers for text messages in groups and private chats."""

    def __init__(
        self,
        router: MessageRouter,
        onboarding_sm: OnboardingStateMachine,
        auth_middleware: AuthMiddleware,
        master_sheet: MasterSheet
    ):
        self.router = router
        self.onboarding_sm = onboarding_sm
        self.auth_middleware = auth_middleware
        self.master_sheet = master_sheet

    async def handle_group_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle messages in group chats."""
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user

        if not message or not message.text or not chat or not user:
            return

        chat_id = chat.id
        user_id = user.id
        text = message.text.strip()

        logger.info(f"Group message from {user_id} in {chat_id}: {text[:50]}...")

        try:
            group_data = await self.master_sheet.get_group(chat_id)

            if not group_data:
                current_state = await self.onboarding_sm.get_state(chat_id)

                if current_state != OnboardingState.INACTIVE:
                    await self._handle_onboarding_message(
                        update, context, chat_id, user_id, text
                    )
                    return

                return

            if group_data.get("status") != "active":
                current_state = await self.onboarding_sm.get_state(chat_id)
                if current_state != OnboardingState.INACTIVE:
                    await self._handle_onboarding_message(
                        update, context, chat_id, user_id, text
                    )
                return

            bot_username = (await context.bot.get_me()).username
            is_mentioned = f"@{bot_username}" in text

            is_reply_to_bot = (
                message.reply_to_message and
                message.reply_to_message.from_user and
                message.reply_to_message.from_user.id == context.bot.id
            )

            should_respond = is_mentioned or is_reply_to_bot

            if is_mentioned:
                text = text.replace(f"@{bot_username}", "").strip()

            response = await self.router.route_message(
                chat_id=chat_id,
                user_id=user_id,
                username=user.username or user.first_name,
                text=text,
                is_group=True,
                should_respond=should_respond,
                reply_to_message_id=message.message_id if should_respond else None
            )

            if response and should_respond:
                await message.reply_text(response)

        except GroupNotFoundError:
            logger.warning(f"Group {chat_id} not found in master sheet")
        except ProcessingError as e:
            logger.error(f"Error processing group message: {e}")
            if is_mentioned or is_reply_to_bot:
                await message.reply_text(
                    "Maaf, terjadi kesalahan saat memproses pesan. Silakan coba lagi."
                )
        except Exception as e:
            logger.error(f"Unexpected error in group message handler: {e}")

    async def handle_private_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle messages in private chats."""
        message = update.effective_message
        user = update.effective_user

        if not message or not message.text or not user:
            return

        user_id = user.id
        text = message.text.strip()

        logger.info(f"Private message from {user_id}: {text[:50]}...")

        try:
            is_admin = await self.auth_middleware.is_super_admin(user_id)

            if is_admin:
                response = await self.router.route_admin_message(
                    user_id=user_id,
                    username=user.username or user.first_name,
                    text=text
                )
            else:
                response = await self.router.route_private_message(
                    user_id=user_id,
                    username=user.username or user.first_name,
                    text=text
                )

            if response:
                await message.reply_text(response)

        except ProcessingError as e:
            logger.error(f"Error processing private message: {e}")
            await message.reply_text(
                "Maaf, terjadi kesalahan saat memproses pesan. Silakan coba lagi."
            )
        except Exception as e:
            logger.error(f"Unexpected error in private message handler: {e}")
            await message.reply_text(
                "Terjadi kesalahan. Silakan coba lagi nanti."
            )

    async def _handle_onboarding_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        user_id: int,
        text: str
    ) -> None:
        """Handle messages during onboarding flow."""
        try:
            is_admin = await self._is_chat_admin(update, context, user_id)

            if not is_admin:
                return

            response, next_action = await self.onboarding_sm.process_input(
                chat_id=chat_id,
                user_id=user_id,
                text=text
            )

            if response:
                await update.effective_message.reply_text(response)

        except Exception as e:
            logger.error(f"Error in onboarding message handler: {e}")

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
