# path: app/core/ai_engine.py
"""
AI Engine - Interface for LLM-powered responses.
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import aiohttp

from app.infra.logger import get_logger
from app.infra.exceptions import AIEngineError


logger = get_logger(__name__)


@dataclass
class AIResponse:
    """Represents an AI response."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str


class AIEngine:
    """
    AI Engine for generating responses using OpenAI-compatible APIs.

    Supports:
    - OpenAI GPT models
    - Anthropic Claude (via proxy)
    - Local models (Ollama, etc.)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        api_base_url: str = "https://api.openai.com/v1"
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_base_url = api_base_url

        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._total_tokens = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate an AI response.

        Args:
            user_message: The user's message
            system_prompt: The system prompt for context
            conversation_history: Previous messages in the conversation
            context_data: Additional context data

        Returns:
            The generated response text
        """
        logger.debug(f"Generating response for: {user_message[:50]}...")

        messages = self._build_messages(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            context_data=context_data
        )

        try:
            response = await self._call_api(messages)
            return response.content

        except Exception as e:
            logger.error(f"AI generation error: {e}")
            raise AIEngineError(f"Failed to generate response: {e}")

    def _build_messages(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Build the messages array for the API call."""
        messages = []

        full_system_prompt = system_prompt
        if context_data:
            context_str = self._format_context(context_data)
            full_system_prompt += f"\n\nKONTEKS TAMBAHAN:\n{context_str}"

        messages.append({
            "role": "system",
            "content": full_system_prompt
        })

        if conversation_history:
            messages.extend(conversation_history[-10:])

        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def _format_context(self, context_data: Dict[str, Any]) -> str:
        """Format context data into a string."""
        formatted = []

        if "financial_summary" in context_data:
            fin = context_data["financial_summary"]
            formatted.append(
                f"Saldo: Rp {fin.get('current_balance', 0):,.0f}, "
                f"Pemasukan: Rp {fin.get('total_income', 0):,.0f}, "
                f"Pengeluaran: Rp {fin.get('total_expense', 0):,.0f}"
            )

        if "user_profile" in context_data:
            user = context_data["user_profile"]
            formatted.append(f"User: {user.get('username', 'Unknown')}")

        if "current_time" in context_data:
            formatted.append(f"Waktu: {context_data['current_time']}")

        return "\n".join(formatted)

    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        retry_count: int = 3
    ) -> AIResponse:
        """Call the AI API with retry logic."""
        session = await self._get_session()

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        last_error = None

        for attempt in range(retry_count):
            try:
                async with session.post(
                    f"{self.api_base_url}/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        return self._parse_response(data)

                    elif response.status == 429:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)

                    else:
                        error_text = await response.text()
                        raise AIEngineError(
                            f"API error {response.status}: {error_text}"
                        )

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"API call failed (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2 ** attempt)

        raise AIEngineError(f"API call failed after {retry_count} attempts: {last_error}")

    def _parse_response(self, data: Dict[str, Any]) -> AIResponse:
        """Parse the API response."""
        self._request_count += 1

        choice = data["choices"][0]
        usage = data.get("usage", {})

        self._total_tokens += usage.get("total_tokens", 0)

        return AIResponse(
            content=choice["message"]["content"],
            model=data.get("model", self.model),
            usage=usage,
            finish_reason=choice.get("finish_reason", "")
        )

    async def generate_with_functions(
        self,
        user_message: str,
        system_prompt: str,
        functions: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate response with function calling capability.

        Args:
            user_message: The user's message
            system_prompt: The system prompt
            functions: List of available functions
            conversation_history: Previous messages

        Returns:
            Dict with either 'content' or 'function_call'
        """
        messages = self._build_messages(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history
        )

        session = await self._get_session()

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "functions": functions,
            "function_call": "auto"
        }

        try:
            async with session.post(
                f"{self.api_base_url}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.status != 200:
                    error_text = await response.text()
                    raise AIEngineError(f"API error: {error_text}")

                data = await response.json()
                choice = data["choices"][0]
                message = choice["message"]

                if "function_call" in message:
                    return {
                        "type": "function_call",
                        "function_name": message["function_call"]["name"],
                        "arguments": json.loads(
                            message["function_call"]["arguments"]
                        )
                    }
                else:
                    return {
                        "type": "content",
                        "content": message["content"]
                    }

        except Exception as e:
            logger.error(f"Function call error: {e}")
            raise AIEngineError(f"Function call failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "model": self.model,
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens
        }


class AIFunctionRegistry:
    """Registry for AI callable functions."""

    def __init__(self):
        self._functions: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: callable
    ) -> None:
        """Register a function."""
        self._functions[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler
        }

    def get_schema(self) -> List[Dict[str, Any]]:
        """Get function schemas for API."""
        return [
            {
                "name": f["name"],
                "description": f["description"],
                "parameters": f["parameters"]
            }
            for f in self._functions.values()
        ]

    async def execute(
        self,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Execute a registered function."""
        if function_name not in self._functions:
            raise ValueError(f"Unknown function: {function_name}")

        handler = self._functions[function_name]["handler"]

        if asyncio.iscoroutinefunction(handler):
            return await handler(**arguments)
        else:
            return handler(**arguments)


def create_transaction_functions() -> List[Dict[str, Any]]:
    """Create function definitions for transaction handling."""
    return [
        {
            "name": "add_transaction",
            "description": "Add a new financial transaction (income or expense)",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["income", "expense"],
                        "description": "Type of transaction"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Transaction amount in IDR"
                    },
                    "description": {
                        "type": "string",
                        "description": "Transaction description"
                    },
                    "category": {
                        "type": "string",
                        "description": "Transaction category (optional)"
                    }
                },
                "required": ["type", "amount", "description"]
            }
        },
        {
            "name": "get_balance",
            "description": "Get current balance and financial summary",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_report",
            "description": "Get financial report for a period",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["week", "month", "year"],
                        "description": "Report period"
                    }
                },
                "required": ["period"]
            }
        }
    ]
