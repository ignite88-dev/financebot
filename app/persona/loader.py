# path: app/persona/loader.py
"""
Persona Loader - Loads and manages bot personas from spreadsheet.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.sheets.client import SheetsClient
from app.infra.logger import get_logger


logger = get_logger(__name__)


@dataclass
class Persona:
    """Represents a bot persona."""
    name: str
    display_name: str
    system_prompt: str
    greeting: str
    style: str
    is_default: bool = False
    custom_instructions: Optional[str] = None


class PersonaLoader:
    """
    Loads and manages bot personas.

    Personas can be loaded from:
    - Master spreadsheet (global personas)
    - Group spreadsheet (custom personas)
    - Default built-in personas
    """

    DEFAULT_PERSONAS = {
        "professional": Persona(
            name="professional",
            display_name="Profesional",
            system_prompt=(
                "Kamu adalah asisten keuangan profesional untuk grup Telegram. "
                "Gunakan bahasa Indonesia yang formal dan sopan. "
                "Berikan informasi yang akurat, terstruktur, dan mudah dipahami. "
                "Fokus pada data dan fakta keuangan. "
                "Hindari basa-basi yang tidak perlu."
            ),
            greeting="Selamat datang. Saya siap membantu mengelola keuangan grup Anda.",
            style="formal",
            is_default=True
        ),
        "friendly": Persona(
            name="friendly",
            display_name="Ramah",
            system_prompt=(
                "Kamu adalah asisten keuangan yang ramah dan santai untuk grup Telegram. "
                "Gunakan bahasa Indonesia yang casual tapi tetap informatif. "
                "Boleh pakai emoji sesekali untuk membuat percakapan lebih hidup. "
                "Tetap fokus membantu urusan keuangan dengan cara yang menyenangkan."
            ),
            greeting="Hai! 👋 Aku siap bantu urusan keuangan grup nih! Ada yang bisa dibantu?",
            style="casual",
            is_default=False
        ),
        "efficient": Persona(
            name="efficient",
            display_name="Efisien",
            system_prompt=(
                "Kamu adalah asisten keuangan yang sangat efisien. "
                "Berikan jawaban singkat, padat, dan langsung ke inti. "
                "Hindari penjelasan yang bertele-tele. "
                "Fokus pada angka dan data penting saja."
            ),
            greeting="Siap membantu. Ketik perintah atau pertanyaan.",
            style="minimal",
            is_default=False
        ),
        "motivational": Persona(
            name="motivational",
            display_name="Motivasional",
            system_prompt=(
                "Kamu adalah asisten keuangan yang juga memberikan motivasi. "
                "Selain membantu urusan keuangan, berikan kata-kata penyemangat. "
                "Apresiasi pencapaian keuangan grup sekecil apapun. "
                "Dorong anggota untuk terus menabung dan mengelola keuangan dengan baik."
            ),
            greeting="Halo tim! 🌟 Mari kita kelola keuangan dengan semangat! Bersama kita bisa!",
            style="enthusiastic",
            is_default=False
        )
    }

    def __init__(
        self,
        sheets_client: SheetsClient,
        master_spreadsheet_id: Optional[str] = None
    ):
        self.sheets_client = sheets_client
        self.master_spreadsheet_id = master_spreadsheet_id

        self._persona_cache: Dict[str, Persona] = {}
        self._group_personas: Dict[int, str] = {}

    async def load_personas(self) -> None:
        """Load personas from master spreadsheet."""
        logger.info("Loading personas...")

        self._persona_cache = self.DEFAULT_PERSONAS.copy()

        if self.master_spreadsheet_id:
            try:
                values = await self.sheets_client.read_range(
                    self.master_spreadsheet_id,
                    "PERSONAS!A:F"
                )

                for row in values[1:]:
                    if len(row) >= 3:
                        persona = Persona(
                            name=row[0],
                            display_name=row[1] if len(row) > 1 else row[0],
                            system_prompt=row[2] if len(row) > 2 else "",
                            greeting=row[3] if len(row) > 3 else "",
                            style=row[4] if len(row) > 4 else "default",
                            is_default=row[5].lower() == "true" if len(row) > 5 else False
                        )
                        self._persona_cache[persona.name] = persona

                logger.info(f"Loaded {len(self._persona_cache)} personas")

            except Exception as e:
                logger.warning(f"Failed to load personas from sheet: {e}")

    async def get_persona(
        self,
        name: str
    ) -> Persona:
        """
        Get a persona by name.

        Args:
            name: The persona name

        Returns:
            The persona or default if not found
        """
        if name in self._persona_cache:
            return self._persona_cache[name]

        if name in self.DEFAULT_PERSONAS:
            return self.DEFAULT_PERSONAS[name]

        return self.DEFAULT_PERSONAS["professional"]

    async def get_group_persona(
        self,
        chat_id: int,
        group_spreadsheet_id: Optional[str] = None
    ) -> Persona:
        """
        Get the persona for a specific group.

        Args:
            chat_id: The chat ID
            group_spreadsheet_id: The group's spreadsheet ID

        Returns:
            The group's persona
        """
        if chat_id in self._group_personas:
            persona_name = self._group_personas[chat_id]
            return await self.get_persona(persona_name)

        if group_spreadsheet_id:
            try:
                values = await self.sheets_client.read_range(
                    group_spreadsheet_id,
                    "CONFIG!A:B"
                )

                for row in values:
                    if row and row[0] == "persona" and len(row) > 1:
                        persona_name = row[1]
                        self._group_personas[chat_id] = persona_name
                        return await self.get_persona(persona_name)

            except Exception as e:
                logger.warning(f"Failed to get group persona: {e}")

        return await self.get_persona("professional")

    async def set_group_persona(
        self,
        chat_id: int,
        persona_name: str,
        group_spreadsheet_id: Optional[str] = None
    ) -> bool:
        """
        Set the persona for a group.

        Args:
            chat_id: The chat ID
            persona_name: The persona name
            group_spreadsheet_id: The group's spreadsheet ID

        Returns:
            True if successful
        """
        if persona_name not in self._persona_cache and persona_name not in self.DEFAULT_PERSONAS:
            logger.warning(f"Unknown persona: {persona_name}")
            return False

        self._group_personas[chat_id] = persona_name

        if group_spreadsheet_id:
            try:
                row_index = await self.sheets_client.find_row(
                    group_spreadsheet_id,
                    "CONFIG",
                    0,
                    "persona"
                )

                if row_index:
                    await self.sheets_client.write_range(
                        group_spreadsheet_id,
                        f"CONFIG!B{row_index}",
                        [[persona_name]]
                    )

                logger.info(f"Set persona for chat {chat_id} to {persona_name}")
                return True

            except Exception as e:
                logger.error(f"Failed to save persona: {e}")
                return False

        return True

    def get_available_personas(self) -> List[Dict[str, Any]]:
        """
        Get list of available personas.

        Returns:
            List of persona info dicts
        """
        personas = []

        all_personas = {**self.DEFAULT_PERSONAS, **self._persona_cache}

        for name, persona in all_personas.items():
            personas.append({
                "name": persona.name,
                "display_name": persona.display_name,
                "style": persona.style,
                "is_default": persona.is_default,
                "greeting": persona.greeting[:50] + "..." if len(persona.greeting) > 50 else persona.greeting
            })

        return personas

    async def create_custom_persona(
        self,
        chat_id: int,
        name: str,
        display_name: str,
        system_prompt: str,
        greeting: str,
        style: str = "custom",
        group_spreadsheet_id: Optional[str] = None
    ) -> Persona:
        """
        Create a custom persona for a group.

        Args:
            chat_id: The chat ID
            name: Persona name (unique identifier)
            display_name: Display name
            system_prompt: The system prompt
            greeting: Greeting message
            style: Style identifier
            group_spreadsheet_id: The group's spreadsheet ID

        Returns:
            The created persona
        """
        persona = Persona(
            name=f"custom_{chat_id}_{name}",
            display_name=display_name,
            system_prompt=system_prompt,
            greeting=greeting,
            style=style,
            is_default=False,
            custom_instructions=None
        )

        self._persona_cache[persona.name] = persona
        self._group_personas[chat_id] = persona.name

        logger.info(f"Created custom persona for chat {chat_id}: {persona.name}")

        return persona

    def get_system_prompt(
        self,
        persona: Persona,
        group_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get the full system prompt for a persona.

        Args:
            persona: The persona
            group_context: Optional group context to include

        Returns:
            The complete system prompt
        """
        prompt = persona.system_prompt

        if group_context:
            context_parts = []

            if group_context.get("group_name"):
                context_parts.append(f"Nama grup: {group_context['group_name']}")

            if group_context.get("member_count"):
                context_parts.append(f"Jumlah anggota: {group_context['member_count']}")

            if group_context.get("current_balance"):
                context_parts.append(
                    f"Saldo saat ini: Rp {group_context['current_balance']:,.0f}"
                )

            if context_parts:
                prompt += "\n\nKONTEKS GRUP:\n" + "\n".join(context_parts)

        return prompt

    def get_greeting(
        self,
        persona: Persona,
        username: Optional[str] = None
    ) -> str:
        """
        Get a personalized greeting.

        Args:
            persona: The persona
            username: Optional username to personalize

        Returns:
            The greeting message
        """
        greeting = persona.greeting

        if username:
            if "{username}" in greeting:
                greeting = greeting.replace("{username}", username)
            elif not any(name in greeting.lower() for name in ["hai", "halo", "hello"]):
                greeting = f"Hai {username}! " + greeting

        return greeting
