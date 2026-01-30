# path: app/onboarding/state_machine.py
"""
Onboarding State Machine - Manages the group setup flow.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.onboarding.states import OnboardingState, StateData
from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.sheets.group import GroupSheet
from app.sheets.templates import SpreadsheetTemplates
from app.infra.logger import get_logger


logger = get_logger(__name__)


class OnboardingStateMachine:
    """
    State machine for group onboarding process.

    States:
    1. WELCOME - Initial welcome message
    2. SHARE_SHEET - Ask user to share spreadsheet
    3. VALIDATE_ACCESS - Validate bot has access to sheet
    4. INIT_TEMPLATE - Initialize spreadsheet with template
    5. REGISTER_ADMIN - Register in master sheet
    6. ACTIVATE_GROUP - Final activation
    7. COMPLETED - Onboarding complete
    """

    def __init__(
        self,
        sheets_client: SheetsClient,
        master_sheet: MasterSheet
    ):
        self.sheets_client = sheets_client
        self.master_sheet = master_sheet

        self._sessions: Dict[int, StateData] = {}

    async def start_onboarding(
        self,
        chat_id: int,
        chat_title: str,
        admin_user_id: int,
        admin_username: str
    ) -> StateData:
        """
        Start the onboarding process for a group.

        Args:
            chat_id: The chat ID
            chat_title: The group title
            admin_user_id: The admin's user ID
            admin_username: The admin's username

        Returns:
            Initial state data
        """
        logger.info(f"Starting onboarding for chat {chat_id}")

        state_data = StateData(
            chat_id=chat_id,
            chat_title=chat_title,
            admin_user_id=admin_user_id,
            admin_username=admin_username,
            current_state=OnboardingState.WELCOME,
            started_at=datetime.now().isoformat()
        )

        self._sessions[chat_id] = state_data

        return state_data

    async def get_state(self, chat_id: int) -> Optional[StateData]:
        """
        Get the current state for a chat.

        Args:
            chat_id: The chat ID

        Returns:
            State data or None
        """
        return self._sessions.get(chat_id)

    async def advance_state(
        self,
        chat_id: int,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Optional[StateData]:
        """
        Advance to the next state.

        Args:
            chat_id: The chat ID
            input_data: Optional input data for state transition

        Returns:
            Updated state data
        """
        state_data = self._sessions.get(chat_id)
        if not state_data:
            return None

        current_state = state_data.current_state
        input_data = input_data or {}

        logger.info(f"Advancing from state {current_state.value} for chat {chat_id}")

        try:
            if current_state == OnboardingState.WELCOME:
                state_data.current_state = OnboardingState.SHARE_SHEET

            elif current_state == OnboardingState.SHARE_SHEET:
                spreadsheet_url = input_data.get("spreadsheet_url")
                if spreadsheet_url:
                    spreadsheet_id = self._extract_spreadsheet_id(spreadsheet_url)
                    if spreadsheet_id:
                        state_data.spreadsheet_id = spreadsheet_id
                        state_data.spreadsheet_url = spreadsheet_url
                        state_data.current_state = OnboardingState.VALIDATE_ACCESS
                    else:
                        state_data.error = "URL spreadsheet tidak valid"
                else:
                    state_data.current_state = OnboardingState.CREATE_SHEET

            elif current_state == OnboardingState.CREATE_SHEET:
                result = await self._create_spreadsheet(state_data)
                if result:
                    state_data.spreadsheet_id = result["spreadsheet_id"]
                    state_data.spreadsheet_url = result["url"]
                    state_data.current_state = OnboardingState.INIT_TEMPLATE
                else:
                    state_data.error = "Gagal membuat spreadsheet"

            elif current_state == OnboardingState.VALIDATE_ACCESS:
                has_access = await self._validate_access(state_data.spreadsheet_id)
                if has_access:
                    state_data.current_state = OnboardingState.INIT_TEMPLATE
                else:
                    state_data.error = "Bot tidak memiliki akses ke spreadsheet"

            elif current_state == OnboardingState.INIT_TEMPLATE:
                success = await self._init_template(state_data)
                if success:
                    state_data.current_state = OnboardingState.REGISTER_ADMIN

            elif current_state == OnboardingState.REGISTER_ADMIN:
                success = await self._register_in_master(state_data)
                if success:
                    state_data.current_state = OnboardingState.ACTIVATE_GROUP

            elif current_state == OnboardingState.ACTIVATE_GROUP:
                success = await self._activate_group(state_data)
                if success:
                    state_data.current_state = OnboardingState.COMPLETED
                    state_data.completed_at = datetime.now().isoformat()

            self._sessions[chat_id] = state_data
            return state_data

        except Exception as e:
            logger.error(f"Error advancing state: {e}")
            state_data.error = str(e)
            return state_data

    async def process_spreadsheet_url(
        self,
        chat_id: int,
        url: str
    ) -> Optional[StateData]:
        """
        Process a spreadsheet URL during onboarding.

        Args:
            chat_id: The chat ID
            url: The spreadsheet URL

        Returns:
            Updated state data
        """
        return await self.advance_state(
            chat_id,
            {"spreadsheet_url": url}
        )

    async def create_new_spreadsheet(
        self,
        chat_id: int
    ) -> Optional[StateData]:
        """
        Create a new spreadsheet for the group.

        Args:
            chat_id: The chat ID

        Returns:
            Updated state data
        """
        state_data = self._sessions.get(chat_id)
        if not state_data:
            return None

        state_data.current_state = OnboardingState.CREATE_SHEET
        self._sessions[chat_id] = state_data

        return await self.advance_state(chat_id)

    async def complete_onboarding(
        self,
        chat_id: int
    ) -> Optional[StateData]:
        """
        Complete the onboarding process.

        Args:
            chat_id: The chat ID

        Returns:
            Final state data
        """
        state_data = self._sessions.get(chat_id)
        if not state_data:
            return None

        while state_data.current_state != OnboardingState.COMPLETED:
            state_data = await self.advance_state(chat_id)
            if state_data.error:
                break

        return state_data

    async def cancel_onboarding(self, chat_id: int) -> bool:
        """
        Cancel the onboarding process.

        Args:
            chat_id: The chat ID

        Returns:
            True if cancelled
        """
        if chat_id in self._sessions:
            del self._sessions[chat_id]
            return True
        return False

    async def _create_spreadsheet(
        self,
        state_data: StateData
    ) -> Optional[Dict[str, Any]]:
        """Create a new spreadsheet for the group."""
        try:
            template = SpreadsheetTemplates.get_group_template()
            sheet_names = [s["name"] for s in template["sheets"]]

            title = f"Finance - {state_data.chat_title}"

            result = await self.sheets_client.create_spreadsheet(
                title=title,
                sheet_names=sheet_names
            )

            logger.info(f"Created spreadsheet: {result['spreadsheet_id']}")
            return result

        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            return None

    async def _validate_access(self, spreadsheet_id: str) -> bool:
        """Validate bot has access to spreadsheet."""
        try:
            info = await self.sheets_client.get_spreadsheet_info(spreadsheet_id)
            return info is not None
        except Exception:
            return False

    async def _init_template(self, state_data: StateData) -> bool:
        """Initialize spreadsheet with template."""
        try:
            group_sheet = GroupSheet(
                self.sheets_client,
                state_data.spreadsheet_id
            )
            await group_sheet.initialize()

            default_config = SpreadsheetTemplates.get_default_config(
                group_name=state_data.chat_title,
                admin_user_id=state_data.admin_user_id,
                admin_username=state_data.admin_username
            )

            await self.sheets_client.append_rows(
                state_data.spreadsheet_id,
                "CONFIG!A:D",
                default_config
            )

            logger.info(f"Initialized template for {state_data.spreadsheet_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to init template: {e}")
            state_data.error = str(e)
            return False

    async def _register_in_master(self, state_data: StateData) -> bool:
        """Register group in master sheet."""
        try:
            await self.master_sheet.register_group(
                chat_id=state_data.chat_id,
                chat_title=state_data.chat_title,
                spreadsheet_id=state_data.spreadsheet_id,
                spreadsheet_url=state_data.spreadsheet_url,
                admin_user_id=state_data.admin_user_id,
                admin_username=state_data.admin_username
            )

            logger.info(f"Registered group {state_data.chat_id} in master sheet")
            return True

        except Exception as e:
            logger.error(f"Failed to register in master: {e}")
            state_data.error = str(e)
            return False

    async def _activate_group(self, state_data: StateData) -> bool:
        """Activate the group."""
        try:
            await self.master_sheet.update_group_status(
                state_data.chat_id,
                "active"
            )

            logger.info(f"Activated group {state_data.chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to activate group: {e}")
            state_data.error = str(e)
            return False

    def _extract_spreadsheet_id(self, url: str) -> Optional[str]:
        """Extract spreadsheet ID from URL."""
        import re

        patterns = [
            r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
            r"id=([a-zA-Z0-9-_]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        if len(url) > 20 and "/" not in url:
            return url

        return None

    def get_state_message(self, state: OnboardingState) -> str:
        """Get the message for a state."""
        messages = {
            OnboardingState.WELCOME: (
                "Selamat datang di Finance Assistant! 🎉\n\n"
                "Saya akan membantu Anda menyiapkan sistem keuangan untuk grup ini."
            ),
            OnboardingState.SHARE_SHEET: (
                "Silakan bagikan link Google Spreadsheet yang akan digunakan,\n"
                "atau klik tombol di bawah untuk membuat spreadsheet baru."
            ),
            OnboardingState.CREATE_SHEET: "Membuat spreadsheet baru...",
            OnboardingState.VALIDATE_ACCESS: "Memvalidasi akses ke spreadsheet...",
            OnboardingState.INIT_TEMPLATE: "Menyiapkan template spreadsheet...",
            OnboardingState.REGISTER_ADMIN: "Mendaftarkan grup di sistem...",
            OnboardingState.ACTIVATE_GROUP: "Mengaktifkan grup...",
            OnboardingState.COMPLETED: (
                "Setup selesai! ✅\n\n"
                "Grup Anda sudah siap menggunakan Finance Assistant.\n"
                "Ketik /help untuk melihat perintah yang tersedia."
            )
        }
        return messages.get(state, "")
