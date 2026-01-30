# path: app/memory/retriever.py
"""
Memory Retriever - Retrieves relevant context from memory.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from app.memory.recent import RecentMemory
from app.memory.semantic import SemanticMemory
from app.infra.logger import get_logger


logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """Result from memory retrieval."""
    content: str
    source: str
    relevance_score: float
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemoryRetriever:
    """
    Retrieves relevant context from multiple memory sources.

    Combines recent memory and semantic memory for comprehensive retrieval.
    """

    def __init__(
        self,
        recent_memory: RecentMemory,
        semantic_memory: SemanticMemory,
        recent_weight: float = 0.4,
        semantic_weight: float = 0.6
    ):
        self.recent_memory = recent_memory
        self.semantic_memory = semantic_memory
        self.recent_weight = recent_weight
        self.semantic_weight = semantic_weight

    async def retrieve(
        self,
        chat_id: int,
        query: str,
        limit: int = 5,
        include_recent: bool = True,
        include_semantic: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query.

        Args:
            chat_id: The chat ID
            query: The search query
            limit: Maximum results
            include_recent: Include recent memory
            include_semantic: Include semantic memory

        Returns:
            List of relevant context items
        """
        results: List[RetrievalResult] = []

        if include_recent:
            recent_results = await self._retrieve_recent(
                chat_id, query, limit
            )
            results.extend(recent_results)

        if include_semantic:
            semantic_results = await self._retrieve_semantic(
                chat_id, query, limit
            )
            results.extend(semantic_results)

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        results = results[:limit]

        return [
            {
                "content": r.content,
                "source": r.source,
                "relevance_score": r.relevance_score,
                "timestamp": r.timestamp,
                "metadata": r.metadata
            }
            for r in results
        ]

    async def _retrieve_recent(
        self,
        chat_id: int,
        query: str,
        limit: int
    ) -> List[RetrievalResult]:
        """Retrieve from recent memory."""
        results = []

        matches = self.recent_memory.search(chat_id, query, limit=limit * 2)

        for i, entry in enumerate(matches):
            recency_score = 1.0 - (i / (len(matches) or 1))
            relevance = recency_score * self.recent_weight

            results.append(RetrievalResult(
                content=entry.get("message", ""),
                source="recent",
                relevance_score=relevance,
                timestamp=entry.get("timestamp"),
                metadata={
                    "user_id": entry.get("user_id"),
                    "username": entry.get("username"),
                    "intent": entry.get("intent")
                }
            ))

        return results[:limit]

    async def _retrieve_semantic(
        self,
        chat_id: int,
        query: str,
        limit: int
    ) -> List[RetrievalResult]:
        """Retrieve from semantic memory."""
        results = []

        matches = self.semantic_memory.search(chat_id, query, limit=limit)

        for entry, similarity in matches:
            relevance = similarity * self.semantic_weight

            results.append(RetrievalResult(
                content=entry.text,
                source="semantic",
                relevance_score=relevance,
                timestamp=entry.timestamp,
                metadata=entry.metadata
            ))

        return results

    async def retrieve_by_intent(
        self,
        chat_id: int,
        intent: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context by intent.

        Args:
            chat_id: The chat ID
            intent: The intent to search for
            limit: Maximum results

        Returns:
            Relevant context for the intent
        """
        entries = self.recent_memory.get_by_intent(chat_id, intent, limit)

        return [
            {
                "content": e.get("message", ""),
                "source": "intent_match",
                "relevance_score": 1.0,
                "timestamp": e.get("timestamp"),
                "metadata": {
                    "user_id": e.get("user_id"),
                    "username": e.get("username"),
                    "intent": intent
                }
            }
            for e in entries
        ]

    async def retrieve_user_context(
        self,
        chat_id: int,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context for a specific user.

        Args:
            chat_id: The chat ID
            user_id: The user's ID
            limit: Maximum results

        Returns:
            User-specific context
        """
        entries = self.recent_memory.get_by_user(chat_id, user_id, limit)

        return [
            {
                "content": e.get("message", ""),
                "source": "user_history",
                "relevance_score": 1.0,
                "timestamp": e.get("timestamp"),
                "metadata": {
                    "intent": e.get("intent")
                }
            }
            for e in entries
        ]

    async def get_conversation_summary(
        self,
        chat_id: int,
        message_count: int = 20
    ) -> str:
        """
        Get a summary of recent conversation.

        Args:
            chat_id: The chat ID
            message_count: Number of messages to summarize

        Returns:
            Conversation summary
        """
        entries = self.recent_memory.get(chat_id, limit=message_count)

        if not entries:
            return "Tidak ada riwayat percakapan."

        intents = [e.get("intent") for e in entries if e.get("intent")]
        unique_users = len(set(e.get("user_id") for e in entries))

        summary_parts = [
            f"Jumlah pesan: {len(entries)}",
            f"Pengguna aktif: {unique_users}"
        ]

        if intents:
            intent_counts: Dict[str, int] = {}
            for intent in intents:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

            top_intents = sorted(
                intent_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]

            intent_str = ", ".join(f"{i[0]} ({i[1]})" for i in top_intents)
            summary_parts.append(f"Topik utama: {intent_str}")

        return "\n".join(summary_parts)

    async def find_similar_conversations(
        self,
        chat_id: int,
        message: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find similar past conversations.

        Args:
            chat_id: The chat ID
            message: The message to find similar conversations for
            limit: Maximum results

        Returns:
            Similar past conversations
        """
        return await self.retrieve(
            chat_id=chat_id,
            query=message,
            limit=limit,
            include_recent=True,
            include_semantic=True
        )

    def get_retrieval_stats(
        self,
        chat_id: int
    ) -> Dict[str, Any]:
        """
        Get retrieval statistics.

        Args:
            chat_id: The chat ID

        Returns:
            Retrieval statistics
        """
        return {
            "recent_memory_count": self.recent_memory.count(chat_id),
            "semantic_memory_count": self.semantic_memory.count(chat_id),
            "recent_weight": self.recent_weight,
            "semantic_weight": self.semantic_weight
        }
