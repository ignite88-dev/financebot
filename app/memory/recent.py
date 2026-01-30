# path: app/memory/recent.py
"""
Recent Memory - Stores and manages recent conversation history.
"""

from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime

from app.infra.logger import get_logger


logger = get_logger(__name__)


class RecentMemory:
    """
    Manages recent conversation memory using a sliding window approach.

    Uses deques for efficient O(1) append and pop operations.
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self._memories: Dict[int, deque] = {}
        self._metadata: Dict[int, Dict[str, Any]] = {}

    def add(
        self,
        chat_id: int,
        entry: Dict[str, Any]
    ) -> None:
        """
        Add an entry to recent memory.

        Args:
            chat_id: The chat ID
            entry: Memory entry with message data
        """
        if chat_id not in self._memories:
            self._memories[chat_id] = deque(maxlen=self.max_messages)
            self._metadata[chat_id] = {
                "created_at": datetime.now().isoformat(),
                "message_count": 0
            }

        self._memories[chat_id].append(entry)
        self._metadata[chat_id]["message_count"] += 1
        self._metadata[chat_id]["last_updated"] = datetime.now().isoformat()

    def get(
        self,
        chat_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent memory entries.

        Args:
            chat_id: The chat ID
            limit: Maximum entries to return

        Returns:
            List of memory entries (oldest first)
        """
        if chat_id not in self._memories:
            return []

        entries = list(self._memories[chat_id])

        if limit:
            entries = entries[-limit:]

        return entries

    def get_latest(
        self,
        chat_id: int,
        count: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get the latest N entries.

        Args:
            chat_id: The chat ID
            count: Number of entries

        Returns:
            Latest entries (newest first)
        """
        entries = self.get(chat_id)
        return list(reversed(entries[-count:]))

    def clear(self, chat_id: int) -> None:
        """
        Clear memory for a chat.

        Args:
            chat_id: The chat ID
        """
        if chat_id in self._memories:
            self._memories[chat_id].clear()
            self._metadata[chat_id]["message_count"] = 0
            self._metadata[chat_id]["cleared_at"] = datetime.now().isoformat()

        logger.debug(f"Cleared recent memory for chat {chat_id}")

    def get_by_user(
        self,
        chat_id: int,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get entries for a specific user.

        Args:
            chat_id: The chat ID
            user_id: The user's ID
            limit: Maximum entries

        Returns:
            User's memory entries
        """
        entries = self.get(chat_id)

        user_entries = [
            e for e in entries
            if e.get("user_id") == user_id
        ]

        if limit:
            user_entries = user_entries[-limit:]

        return user_entries

    def get_by_intent(
        self,
        chat_id: int,
        intent: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get entries with a specific intent.

        Args:
            chat_id: The chat ID
            intent: The intent to filter by
            limit: Maximum entries

        Returns:
            Matching entries
        """
        entries = self.get(chat_id)

        intent_entries = [
            e for e in entries
            if e.get("intent") == intent
        ]

        if limit:
            intent_entries = intent_entries[-limit:]

        return intent_entries

    def get_metadata(self, chat_id: int) -> Dict[str, Any]:
        """
        Get metadata for a chat's memory.

        Args:
            chat_id: The chat ID

        Returns:
            Memory metadata
        """
        if chat_id not in self._metadata:
            return {
                "exists": False,
                "message_count": 0
            }

        meta = self._metadata[chat_id].copy()
        meta["exists"] = True
        meta["current_size"] = len(self._memories.get(chat_id, []))
        meta["max_size"] = self.max_messages

        return meta

    def search(
        self,
        chat_id: int,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Simple text search in memory.

        Args:
            chat_id: The chat ID
            query: Search query
            limit: Maximum results

        Returns:
            Matching entries
        """
        entries = self.get(chat_id)
        query_lower = query.lower()

        matches = []
        for entry in entries:
            message = entry.get("message", "").lower()
            if query_lower in message:
                matches.append(entry)

        return matches[-limit:]

    def get_conversation_window(
        self,
        chat_id: int,
        window_size: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get conversation formatted for AI context.

        Args:
            chat_id: The chat ID
            window_size: Number of messages

        Returns:
            Formatted conversation history
        """
        entries = self.get(chat_id, limit=window_size)

        formatted = []
        for entry in entries:
            role = entry.get("role", "user")
            content = entry.get("message", "")

            if role == "user":
                username = entry.get("username", "User")
                content = f"[{username}]: {content}"

            formatted.append({
                "role": role,
                "content": content
            })

        return formatted

    def count(self, chat_id: int) -> int:
        """
        Get the number of entries for a chat.

        Args:
            chat_id: The chat ID

        Returns:
            Entry count
        """
        if chat_id not in self._memories:
            return 0
        return len(self._memories[chat_id])

    def exists(self, chat_id: int) -> bool:
        """
        Check if memory exists for a chat.

        Args:
            chat_id: The chat ID

        Returns:
            True if memory exists
        """
        return chat_id in self._memories and len(self._memories[chat_id]) > 0

    def get_all_chat_ids(self) -> List[int]:
        """
        Get all chat IDs with memory.

        Returns:
            List of chat IDs
        """
        return list(self._memories.keys())

    def get_total_entries(self) -> int:
        """
        Get total entries across all chats.

        Returns:
            Total entry count
        """
        return sum(len(m) for m in self._memories.values())
