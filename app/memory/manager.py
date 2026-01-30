# path: app/memory/manager.py
"""
Memory Manager - Orchestrates memory storage and retrieval.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.memory.recent import RecentMemory
from app.memory.semantic import SemanticMemory
from app.memory.retriever import MemoryRetriever
from app.sheets.client import SheetsClient
from app.infra.logger import get_logger


logger = get_logger(__name__)


class MemoryManager:
    """
    Central manager for all memory operations.

    Handles:
    - Recent conversation memory
    - Semantic search memory
    - Memory storage in Google Sheets
    - Context window management
    """

    def __init__(
        self,
        sheets_client: SheetsClient,
        max_recent_messages: int = 50,
        context_window_messages: int = 10
    ):
        self.sheets_client = sheets_client
        self.max_recent_messages = max_recent_messages
        self.context_window_messages = context_window_messages

        self.recent_memory = RecentMemory(
            max_messages=max_recent_messages
        )

        self.semantic_memory = SemanticMemory()

        self.retriever = MemoryRetriever(
            recent_memory=self.recent_memory,
            semantic_memory=self.semantic_memory
        )

        self._group_memories: Dict[int, List[Dict[str, Any]]] = {}

    async def store_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        message: str,
        role: str = "user",
        intent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store a message in memory.

        Args:
            chat_id: The chat ID
            user_id: The user's ID
            username: The user's username
            message: The message content
            role: Message role (user/assistant)
            intent: Detected intent
            metadata: Additional metadata
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "username": username,
            "message": message,
            "role": role,
            "intent": intent,
            "metadata": metadata or {}
        }

        self.recent_memory.add(chat_id, entry)

        if chat_id not in self._group_memories:
            self._group_memories[chat_id] = []

        self._group_memories[chat_id].append(entry)

        if len(self._group_memories[chat_id]) > self.max_recent_messages:
            self._group_memories[chat_id] = self._group_memories[chat_id][-self.max_recent_messages:]

        logger.debug(f"Stored message in memory for chat {chat_id}")

    async def get_conversation_history(
        self,
        chat_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for AI context.

        Args:
            chat_id: The chat ID
            limit: Maximum messages to return

        Returns:
            List of message dicts with 'role' and 'content'
        """
        limit = limit or self.context_window_messages

        messages = self.recent_memory.get(chat_id, limit)

        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg.get("role", "user"),
                "content": msg.get("message", "")
            })

        return formatted

    async def get_relevant_context(
        self,
        chat_id: int,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant context for a query using semantic search.

        Args:
            chat_id: The chat ID
            query: The search query
            limit: Maximum results

        Returns:
            List of relevant memory entries
        """
        return await self.retriever.retrieve(
            chat_id=chat_id,
            query=query,
            limit=limit
        )

    async def get_user_context(
        self,
        chat_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get context specific to a user.

        Args:
            chat_id: The chat ID
            user_id: The user's ID

        Returns:
            User context data
        """
        all_messages = self._group_memories.get(chat_id, [])

        user_messages = [
            m for m in all_messages
            if m.get("user_id") == user_id
        ]

        return {
            "message_count": len(user_messages),
            "recent_messages": user_messages[-5:],
            "common_intents": self._get_common_intents(user_messages)
        }

    async def summarize_context(
        self,
        chat_id: int
    ) -> Dict[str, Any]:
        """
        Get a summary of the chat context.

        Args:
            chat_id: The chat ID

        Returns:
            Context summary
        """
        messages = self._group_memories.get(chat_id, [])

        if not messages:
            return {
                "total_messages": 0,
                "unique_users": 0,
                "recent_topics": [],
                "summary": "No conversation history available."
            }

        unique_users = len(set(m.get("user_id") for m in messages))

        intents = [m.get("intent") for m in messages if m.get("intent")]
        recent_topics = list(set(intents[-10:]))

        return {
            "total_messages": len(messages),
            "unique_users": unique_users,
            "recent_topics": recent_topics,
            "last_activity": messages[-1].get("timestamp") if messages else None
        }

    async def clear_memory(
        self,
        chat_id: int,
        older_than: Optional[datetime] = None
    ) -> int:
        """
        Clear memory for a chat.

        Args:
            chat_id: The chat ID
            older_than: Only clear messages older than this

        Returns:
            Number of messages cleared
        """
        if chat_id not in self._group_memories:
            return 0

        if older_than:
            original_count = len(self._group_memories[chat_id])
            self._group_memories[chat_id] = [
                m for m in self._group_memories[chat_id]
                if datetime.fromisoformat(m["timestamp"]) > older_than
            ]
            cleared = original_count - len(self._group_memories[chat_id])
        else:
            cleared = len(self._group_memories[chat_id])
            self._group_memories[chat_id] = []

        self.recent_memory.clear(chat_id)

        logger.info(f"Cleared {cleared} messages from chat {chat_id}")
        return cleared

    async def get_memory_stats(
        self,
        chat_id: int
    ) -> Dict[str, Any]:
        """
        Get memory statistics for a chat.

        Args:
            chat_id: The chat ID

        Returns:
            Memory statistics
        """
        messages = self._group_memories.get(chat_id, [])

        if not messages:
            return {
                "total_entries": 0,
                "oldest_entry": None,
                "newest_entry": None,
                "memory_usage_bytes": 0
            }

        import sys

        return {
            "total_entries": len(messages),
            "oldest_entry": messages[0].get("timestamp") if messages else None,
            "newest_entry": messages[-1].get("timestamp") if messages else None,
            "memory_usage_bytes": sys.getsizeof(messages)
        }

    def _get_common_intents(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[str]:
        """Get most common intents from messages."""
        intent_counts: Dict[str, int] = {}

        for msg in messages:
            intent = msg.get("intent")
            if intent:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

        sorted_intents = sorted(
            intent_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [intent for intent, _ in sorted_intents[:5]]

    async def export_memory(
        self,
        chat_id: int
    ) -> List[Dict[str, Any]]:
        """
        Export all memory for a chat.

        Args:
            chat_id: The chat ID

        Returns:
            All memory entries
        """
        return self._group_memories.get(chat_id, []).copy()

    async def import_memory(
        self,
        chat_id: int,
        entries: List[Dict[str, Any]]
    ) -> int:
        """
        Import memory entries for a chat.

        Args:
            chat_id: The chat ID
            entries: Memory entries to import

        Returns:
            Number of entries imported
        """
        if chat_id not in self._group_memories:
            self._group_memories[chat_id] = []

        self._group_memories[chat_id].extend(entries)

        self._group_memories[chat_id] = self._group_memories[chat_id][-self.max_recent_messages:]

        return len(entries)
