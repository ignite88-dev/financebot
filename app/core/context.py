# path: app/core/context.py
"""
Context builder - Builds context for AI responses including memory and persona.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.sheets.client import SheetsClient
from app.sheets.group import GroupSheet
from app.memory.manager import MemoryManager
from app.persona.loader import PersonaLoader
from app.infra.logger import get_logger


logger = get_logger(__name__)


class ContextBuilder:
    """
    Builds comprehensive context for AI responses.

    Combines:
    - Group configuration and settings
    - Recent conversation history
    - Semantic memory retrieval
    - Persona and style information
    - Current financial data
    """

    def __init__(
        self,
        sheets_client: SheetsClient,
        memory_manager: MemoryManager,
        persona_loader: PersonaLoader
    ):
        self.sheets_client = sheets_client
        self.memory_manager = memory_manager
        self.persona_loader = persona_loader

    async def build_context(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        current_message: str,
        include_financials: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete context for AI response generation.

        Args:
            chat_id: The group chat ID
            user_id: The user's ID
            username: The user's username
            current_message: The current message text
            include_financials: Whether to include financial data

        Returns:
            Dict containing system_prompt, conversation_history, and context_data
        """
        logger.debug(f"Building context for chat {chat_id}, user {user_id}")

        group_config = await self._get_group_config(chat_id)

        persona = await self.persona_loader.get_persona(
            chat_id=chat_id,
            persona_id=group_config.get("persona_id", "friendly")
        )

        recent_messages = await self.memory_manager.get_recent_messages(
            chat_id=chat_id,
            limit=10
        )

        relevant_memories = await self.memory_manager.retrieve_relevant(
            chat_id=chat_id,
            query=current_message,
            limit=5
        )

        user_profile = await self._get_user_profile(chat_id, user_id, username)

        context_data = {
            "group_name": group_config.get("name", "Unknown Group"),
            "group_settings": group_config,
            "user_profile": user_profile,
            "current_time": datetime.now().isoformat(),
            "relevant_context": relevant_memories
        }

        if include_financials:
            financial_context = await self._get_financial_context(chat_id)
            context_data["financial_summary"] = financial_context

        system_prompt = self._build_system_prompt(
            persona=persona,
            context_data=context_data
        )

        conversation_history = self._format_conversation_history(
            recent_messages=recent_messages,
            user_id=user_id
        )

        return {
            "system_prompt": system_prompt,
            "conversation_history": conversation_history,
            "context_data": context_data
        }

    async def _get_group_config(self, chat_id: int) -> Dict[str, Any]:
        """Get group configuration from sheets."""
        try:
            group_data = await self.sheets_client.get_group_config(chat_id)
            return group_data or {
                "name": "Unknown Group",
                "language": "id",
                "currency": "IDR",
                "persona_id": "friendly"
            }
        except Exception as e:
            logger.error(f"Error getting group config: {e}")
            return {
                "name": "Unknown Group",
                "language": "id",
                "currency": "IDR",
                "persona_id": "friendly"
            }

    async def _get_user_profile(
        self,
        chat_id: int,
        user_id: int,
        username: str
    ) -> Dict[str, Any]:
        """Get or create user profile."""
        try:
            profile = await self.sheets_client.get_user_profile(chat_id, user_id)

            if not profile:
                profile = {
                    "user_id": user_id,
                    "username": username,
                    "first_seen": datetime.now().isoformat(),
                    "message_count": 0,
                    "transaction_count": 0
                }

            return profile
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {
                "user_id": user_id,
                "username": username
            }

    async def _get_financial_context(self, chat_id: int) -> Dict[str, Any]:
        """Get current financial context for the group."""
        try:
            group_data = await self.sheets_client.get_group_config(chat_id)
            if not group_data or not group_data.get("spreadsheet_id"):
                return {}

            group_sheet = GroupSheet(
                self.sheets_client,
                group_data["spreadsheet_id"]
            )

            balance_data = await group_sheet.get_balance()

            recent_transactions = await group_sheet.get_recent_transactions(5)

            return {
                "current_balance": balance_data.get("balance", 0),
                "total_income": balance_data.get("total_income", 0),
                "total_expense": balance_data.get("total_expense", 0),
                "recent_transactions": recent_transactions,
                "currency": group_data.get("currency", "IDR")
            }
        except Exception as e:
            logger.error(f"Error getting financial context: {e}")
            return {}

    def _build_system_prompt(
        self,
        persona: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> str:
        """Build the system prompt for AI."""
        group_name = context_data.get("group_name", "grup ini")
        financial_summary = context_data.get("financial_summary", {})

        base_prompt = f"""Kamu adalah asisten keuangan AI untuk grup "{group_name}" di Telegram.

{persona.get('description', '')}

GAYA KOMUNIKASI:
{persona.get('style', 'Ramah dan informatif')}

KEMAMPUAN:
- Mencatat transaksi pemasukan dan pengeluaran
- Memberikan informasi saldo dan laporan keuangan
- Menjawab pertanyaan tentang keuangan grup
- Memberikan saran pengelolaan keuangan

KONTEKS KEUANGAN SAAT INI:
"""

        if financial_summary:
            base_prompt += f"""
- Saldo saat ini: Rp {financial_summary.get('current_balance', 0):,.0f}
- Total pemasukan: Rp {financial_summary.get('total_income', 0):,.0f}
- Total pengeluaran: Rp {financial_summary.get('total_expense', 0):,.0f}
"""
        else:
            base_prompt += "\n- Data keuangan belum tersedia\n"

        if context_data.get("relevant_context"):
            base_prompt += "\nKONTEKS RELEVAN DARI PERCAKAPAN SEBELUMNYA:\n"
            for memory in context_data["relevant_context"][:3]:
                base_prompt += f"- {memory.get('content', '')}\n"

        base_prompt += """
INSTRUKSI:
1. Selalu jawab dalam Bahasa Indonesia kecuali diminta lain
2. Untuk transaksi, konfirmasi detail sebelum mencatat
3. Berikan respons yang singkat dan informatif
4. Jika tidak yakin, minta klarifikasi
5. Jangan mengada-ada data yang tidak ada
"""

        return base_prompt

    def _format_conversation_history(
        self,
        recent_messages: List[Dict[str, Any]],
        user_id: int
    ) -> List[Dict[str, str]]:
        """Format recent messages into conversation history."""
        history = []

        for msg in recent_messages:
            role = "user" if msg.get("user_id") != "bot" else "assistant"
            content = msg.get("content", msg.get("message", ""))

            if content:
                history.append({
                    "role": role,
                    "content": content
                })

        return history[-10:]


class ContextCache:
    """Cache for context data to reduce API calls."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached context."""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now().timestamp() - entry["timestamp"] < self.ttl_seconds:
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Set cached context."""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now().timestamp()
        }

    def invalidate(self, key: str) -> None:
        """Invalidate cached entry."""
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
