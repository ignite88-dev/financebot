# path: app/memory/semantic.py
"""
Semantic Memory - Handles semantic search and embedding-based retrieval.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import math

from app.infra.logger import get_logger


logger = get_logger(__name__)


@dataclass
class MemoryEntry:
    """Represents a memory entry with embedding."""
    id: str
    text: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class SemanticMemory:
    """
    Semantic memory using simple TF-IDF-like approach.

    For production, this should be replaced with proper embeddings
    (OpenAI embeddings, sentence-transformers, etc.)
    """

    def __init__(self):
        self._memories: Dict[int, List[MemoryEntry]] = {}
        self._word_frequencies: Dict[int, Dict[str, int]] = {}
        self._document_counts: Dict[int, int] = {}

    def add(
        self,
        chat_id: int,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None
    ) -> str:
        """
        Add a memory entry.

        Args:
            chat_id: The chat ID
            text: The text content
            metadata: Additional metadata
            timestamp: Entry timestamp

        Returns:
            The entry ID
        """
        if chat_id not in self._memories:
            self._memories[chat_id] = []
            self._word_frequencies[chat_id] = {}
            self._document_counts[chat_id] = 0

        entry_id = self._generate_id(text)

        entry = MemoryEntry(
            id=entry_id,
            text=text,
            embedding=self._compute_embedding(text),
            metadata=metadata,
            timestamp=timestamp
        )

        self._memories[chat_id].append(entry)
        self._update_frequencies(chat_id, text)
        self._document_counts[chat_id] += 1

        return entry_id

    def search(
        self,
        chat_id: int,
        query: str,
        limit: int = 5,
        threshold: float = 0.1
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Search for similar memories.

        Args:
            chat_id: The chat ID
            query: The search query
            limit: Maximum results
            threshold: Minimum similarity threshold

        Returns:
            List of (entry, similarity_score) tuples
        """
        if chat_id not in self._memories:
            return []

        query_embedding = self._compute_embedding(query)

        results = []
        for entry in self._memories[chat_id]:
            if entry.embedding:
                similarity = self._cosine_similarity(
                    query_embedding,
                    entry.embedding
                )
                if similarity >= threshold:
                    results.append((entry, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_related(
        self,
        chat_id: int,
        entry_id: str,
        limit: int = 5
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Get entries related to a specific entry.

        Args:
            chat_id: The chat ID
            entry_id: The entry ID to find related entries for
            limit: Maximum results

        Returns:
            Related entries with similarity scores
        """
        if chat_id not in self._memories:
            return []

        target_entry = None
        for entry in self._memories[chat_id]:
            if entry.id == entry_id:
                target_entry = entry
                break

        if not target_entry or not target_entry.embedding:
            return []

        results = []
        for entry in self._memories[chat_id]:
            if entry.id != entry_id and entry.embedding:
                similarity = self._cosine_similarity(
                    target_entry.embedding,
                    entry.embedding
                )
                results.append((entry, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def clear(self, chat_id: int) -> None:
        """Clear all memories for a chat."""
        if chat_id in self._memories:
            self._memories[chat_id] = []
            self._word_frequencies[chat_id] = {}
            self._document_counts[chat_id] = 0

    def count(self, chat_id: int) -> int:
        """Get the number of memories for a chat."""
        return len(self._memories.get(chat_id, []))

    def _generate_id(self, text: str) -> str:
        """Generate a unique ID for an entry."""
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def _compute_embedding(self, text: str) -> List[float]:
        """
        Compute a simple TF-based embedding.

        For production, replace with proper embeddings.
        """
        words = self._tokenize(text)

        word_counts: Dict[str, int] = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

        vocab = sorted(set(words))
        if not vocab:
            return [0.0]

        embedding = []
        for word in vocab:
            tf = word_counts.get(word, 0) / len(words) if words else 0
            embedding.append(tf)

        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        text = text.lower()

        words = []
        current_word = []

        for char in text:
            if char.isalnum():
                current_word.append(char)
            else:
                if current_word:
                    words.append("".join(current_word))
                    current_word = []

        if current_word:
            words.append("".join(current_word))

        stopwords = {
            "yang", "dan", "di", "ke", "dari", "untuk", "dengan",
            "ini", "itu", "pada", "adalah", "juga", "tidak",
            "the", "a", "an", "is", "are", "was", "were", "be",
            "been", "being", "have", "has", "had", "do", "does"
        }

        words = [w for w in words if w not in stopwords and len(w) > 1]

        return words

    def _update_frequencies(self, chat_id: int, text: str) -> None:
        """Update word frequencies for a chat."""
        words = self._tokenize(text)

        for word in set(words):
            self._word_frequencies[chat_id][word] = (
                self._word_frequencies[chat_id].get(word, 0) + 1
            )

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len]
        vec2 = vec2[:min_len]

        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        norm1 = math.sqrt(sum(x * x for x in vec1))
        norm2 = math.sqrt(sum(x * x for x in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def get_keywords(
        self,
        chat_id: int,
        limit: int = 10
    ) -> List[Tuple[str, int]]:
        """
        Get top keywords for a chat.

        Args:
            chat_id: The chat ID
            limit: Maximum keywords

        Returns:
            List of (keyword, count) tuples
        """
        if chat_id not in self._word_frequencies:
            return []

        sorted_words = sorted(
            self._word_frequencies[chat_id].items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_words[:limit]

    def get_entry(
        self,
        chat_id: int,
        entry_id: str
    ) -> Optional[MemoryEntry]:
        """Get a specific entry by ID."""
        if chat_id not in self._memories:
            return None

        for entry in self._memories[chat_id]:
            if entry.id == entry_id:
                return entry

        return None

    def get_all(
        self,
        chat_id: int
    ) -> List[MemoryEntry]:
        """Get all entries for a chat."""
        return self._memories.get(chat_id, []).copy()
