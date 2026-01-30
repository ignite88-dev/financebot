# path: app/bot/middleware/auth.py
"""
Authentication middleware for bot commands and actions.
"""

from typing import Optional, List, Set
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from app.sheets.master import MasterSheet
from app.infra.logger import get_logger
from app.config.settings import get_settings


logger = get_logger(__name__)


class AuthMiddleware:
    """
    Middleware for handling authentication and authorization.
    """

    def __init__(self, master_sheet: MasterSheet):
        self.master_sheet = master_sheet
        self.settings = get_settings()
        self._super_admin_cache: Set[int] = set()
        self._group_admin_cache: dict = {}

    async def is_super_admin(self, user_id: int) -> bool:
        """
        Check if a user is a super admin.

        Super admins have full access to all bot features across all groups.
        """
        if user_id in self._super_admin_cache:
            return True

        super_admin_ids = self.settings.super_admin_ids

        if user_id in super_admin_ids:
            self._super_admin_cache.add(user_id)
            return True

        try:
            admin_data = await self.master_sheet.get_super_admins()
            admin_ids = {int(admin["user_id"]) for admin in admin_data}

            if user_id in admin_ids:
                self._super_admin_cache.add(user_id)
                return True
        except Exception as e:
            logger.error(f"Error checking super admin status: {e}")

        return False

    async def is_group_admin(
        self,
        user_id: int,
        chat_id: int,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None
    ) -> bool:
        """
        Check if a user is an admin of a specific group.
        """
        cache_key = f"{chat_id}:{user_id}"
        if cache_key in self._group_admin_cache:
            return self._group_admin_cache[cache_key]

        try:
            group_data = await self.master_sheet.get_group(chat_id)
            if group_data:
                admin_ids = group_data.get("admin_ids", [])
                if user_id in admin_ids:
                    self._group_admin_cache[cache_key] = True
                    return True

            if context:
                member = await context.bot.get_chat_member(chat_id, user_id)
                is_admin = member.status in ["creator", "administrator"]
                self._group_admin_cache[cache_key] = is_admin
                return is_admin

        except Exception as e:
            logger.error(f"Error checking group admin status: {e}")

        return False

    async def is_group_member(
        self,
        user_id: int,
        chat_id: int,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None
    ) -> bool:
        """
        Check if a user is a member of a specific group.
        """
        try:
            if context:
                member = await context.bot.get_chat_member(chat_id, user_id)
                return member.status not in ["left", "kicked"]
        except Exception as e:
            logger.error(f"Error checking group membership: {e}")

        return False

    async def validate_group_access(
        self,
        user_id: int,
        chat_id: int,
        required_role: str = "member"
    ) -> bool:
        """
        Validate user's access to a group based on required role.

        Args:
            user_id: The user's Telegram ID
            chat_id: The group's chat ID
            required_role: Required role (member, admin, super_admin)
        """
        if await self.is_super_admin(user_id):
            return True

        if required_role == "super_admin":
            return False

        if required_role == "admin":
            return await self.is_group_admin(user_id, chat_id)

        group_data = await self.master_sheet.get_group(chat_id)
        if group_data and group_data.get("status") == "active":
            return True

        return False

    def clear_cache(self, chat_id: Optional[int] = None) -> None:
        """
        Clear the authentication cache.

        Args:
            chat_id: Optional chat ID to clear specific group cache
        """
        if chat_id:
            keys_to_remove = [
                k for k in self._group_admin_cache
                if k.startswith(f"{chat_id}:")
            ]
            for key in keys_to_remove:
                del self._group_admin_cache[key]
        else:
            self._group_admin_cache.clear()
            self._super_admin_cache.clear()

        logger.debug(f"Auth cache cleared for chat_id={chat_id}")


def require_admin(func):
    """
    Decorator to require group admin privileges for a handler.
    """
    @wraps(func)
    async def wrapper(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ):
        user = update.effective_user
        chat = update.effective_chat

        if not user or not chat:
            return

        auth_middleware = getattr(self, "auth_middleware", None)
        if not auth_middleware:
            logger.error("AuthMiddleware not found in handler class")
            return

        is_admin = await auth_middleware.is_group_admin(
            user.id, chat.id, context
        )

        if not is_admin:
            await update.effective_message.reply_text(
                "Anda memerlukan hak admin untuk menjalankan perintah ini."
            )
            return

        return await func(self, update, context, *args, **kwargs)

    return wrapper


def require_super_admin(func):
    """
    Decorator to require super admin privileges for a handler.
    """
    @wraps(func)
    async def wrapper(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ):
        user = update.effective_user

        if not user:
            return

        auth_middleware = getattr(self, "auth_middleware", None)
        if not auth_middleware:
            logger.error("AuthMiddleware not found in handler class")
            return

        is_super_admin = await auth_middleware.is_super_admin(user.id)

        if not is_super_admin:
            await update.effective_message.reply_text(
                "Anda memerlukan hak super admin untuk menjalankan perintah ini."
            )
            return

        return await func(self, update, context, *args, **kwargs)

    return wrapper


def require_active_group(func):
    """
    Decorator to require the group to be active.
    """
    @wraps(func)
    async def wrapper(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ):
        chat = update.effective_chat

        if not chat or chat.type == "private":
            return await func(self, update, context, *args, **kwargs)

        master_sheet = getattr(self, "master_sheet", None)
        if not master_sheet:
            logger.error("MasterSheet not found in handler class")
            return

        group_data = await master_sheet.get_group(chat.id)

        if not group_data or group_data.get("status") != "active":
            await update.effective_message.reply_text(
                "Grup ini belum aktif. Jalankan /setup untuk memulai."
            )
            return

        return await func(self, update, context, *args, **kwargs)

    return wrapper
