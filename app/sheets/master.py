# path: app/sheets/master.py
"""
Master sheet - Manages the master admin spreadsheet with all groups.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.sheets.client import SheetsClient
from app.sheets.schema import SheetSchema
from app.infra.logger import get_logger
from app.infra.exceptions import SheetsError


logger = get_logger(__name__)


class MasterSheet:
    """
    Manages the master admin spreadsheet.

    The master sheet contains:
    - GROUPS: All registered groups
    - SUPER_ADMINS: Super admin users
    - SETTINGS: Global bot settings
    - LOGS: System logs
    - STATS: Aggregated statistics
    """

    SHEET_GROUPS = "GROUPS"
    SHEET_SUPER_ADMINS = "SUPER_ADMINS"
    SHEET_SETTINGS = "SETTINGS"
    SHEET_LOGS = "LOGS"
    SHEET_STATS = "STATS"

    GROUPS_HEADERS = [
        "chat_id", "name", "spreadsheet_id", "spreadsheet_url",
        "status", "admin_user_id", "admin_username", "created_at",
        "updated_at", "member_count", "transaction_count", "notes"
    ]

    def __init__(
        self,
        sheets_client: SheetsClient,
        spreadsheet_id: str
    ):
        self.sheets_client = sheets_client
        self.spreadsheet_id = spreadsheet_id

        self._groups_cache: Dict[int, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 60

    async def initialize(self) -> None:
        """Initialize and validate the master sheet."""
        logger.info("Initializing master sheet...")

        try:
            info = await self.sheets_client.get_spreadsheet_info(
                self.spreadsheet_id
            )

            existing_sheets = info.get("sheets", [])

            required_sheets = [
                self.SHEET_GROUPS,
                self.SHEET_SUPER_ADMINS,
                self.SHEET_SETTINGS,
                self.SHEET_LOGS,
                self.SHEET_STATS
            ]

            for sheet_name in required_sheets:
                if sheet_name not in existing_sheets:
                    await self.sheets_client.add_sheet(
                        self.spreadsheet_id,
                        sheet_name
                    )
                    logger.info(f"Created sheet: {sheet_name}")

            await self._ensure_headers()

            logger.info("Master sheet initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize master sheet: {e}")
            raise SheetsError(f"Master sheet initialization failed: {e}")

    async def _ensure_headers(self) -> None:
        """Ensure all sheets have proper headers."""
        groups_data = await self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.SHEET_GROUPS}!A1:L1"
        )

        if not groups_data or groups_data[0] != self.GROUPS_HEADERS:
            await self.sheets_client.write_range(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A1:L1",
                [self.GROUPS_HEADERS]
            )

        admins_headers = ["user_id", "username", "added_at", "added_by", "status"]
        admins_data = await self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.SHEET_SUPER_ADMINS}!A1:E1"
        )

        if not admins_data:
            await self.sheets_client.write_range(
                self.spreadsheet_id,
                f"{self.SHEET_SUPER_ADMINS}!A1:E1",
                [admins_headers]
            )

        settings_headers = ["key", "value", "description", "updated_at"]
        settings_data = await self.sheets_client.read_range(
            self.spreadsheet_id,
            f"{self.SHEET_SETTINGS}!A1:D1"
        )

        if not settings_data:
            await self.sheets_client.write_range(
                self.spreadsheet_id,
                f"{self.SHEET_SETTINGS}!A1:D1",
                [settings_headers]
            )

    async def get_group(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a group by chat ID.

        Args:
            chat_id: The Telegram chat ID

        Returns:
            Group data dict or None if not found
        """
        if self._is_cache_valid() and chat_id in self._groups_cache:
            return self._groups_cache[chat_id]

        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A:L"
            )

            self._groups_cache.clear()
            self._cache_timestamp = datetime.now()

            for row in values[1:]:
                if len(row) >= 8:
                    row_chat_id = int(row[0]) if row[0] else 0
                    group_data = self._row_to_group_dict(row)
                    self._groups_cache[row_chat_id] = group_data

                    await self.sheets_client.set_group_config(
                        row_chat_id,
                        group_data
                    )

            return self._groups_cache.get(chat_id)

        except Exception as e:
            logger.error(f"Error getting group {chat_id}: {e}")
            return None

    async def get_all_groups(self) -> List[Dict[str, Any]]:
        """Get all registered groups."""
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A:L"
            )

            groups = []
            for row in values[1:]:
                if len(row) >= 5:
                    groups.append(self._row_to_group_dict(row))

            return groups

        except Exception as e:
            logger.error(f"Error getting all groups: {e}")
            return []

    async def register_group(
        self,
        chat_id: int,
        name: str,
        spreadsheet_id: str,
        spreadsheet_url: str,
        admin_user_id: int,
        admin_username: str,
        status: str = "pending"
    ) -> Dict[str, Any]:
        """
        Register a new group.

        Args:
            chat_id: Telegram chat ID
            name: Group name
            spreadsheet_id: The group's spreadsheet ID
            spreadsheet_url: The group's spreadsheet URL
            admin_user_id: Admin's Telegram user ID
            admin_username: Admin's username
            status: Initial status (pending, active, inactive)

        Returns:
            The created group data
        """
        logger.info(f"Registering group: {name} ({chat_id})")

        existing = await self.get_group(chat_id)
        if existing:
            return await self.update_group(
                chat_id,
                name=name,
                spreadsheet_id=spreadsheet_id,
                spreadsheet_url=spreadsheet_url,
                status=status
            )

        now = datetime.now().isoformat()

        row = [
            str(chat_id),
            name,
            spreadsheet_id,
            spreadsheet_url,
            status,
            str(admin_user_id),
            admin_username,
            now,
            now,
            "0",
            "0",
            ""
        ]

        try:
            await self.sheets_client.append_rows(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A:L",
                [row]
            )

            group_data = self._row_to_group_dict(row)
            self._groups_cache[chat_id] = group_data

            await self.sheets_client.set_group_config(chat_id, group_data)

            logger.info(f"Group registered: {chat_id}")

            return group_data

        except Exception as e:
            logger.error(f"Error registering group: {e}")
            raise SheetsError(f"Failed to register group: {e}")

    async def update_group(
        self,
        chat_id: int,
        **updates
    ) -> Dict[str, Any]:
        """
        Update a group's data.

        Args:
            chat_id: The chat ID
            **updates: Fields to update

        Returns:
            Updated group data
        """
        logger.info(f"Updating group {chat_id}: {list(updates.keys())}")

        try:
            row_index = await self.sheets_client.find_row(
                self.spreadsheet_id,
                self.SHEET_GROUPS,
                0,
                str(chat_id)
            )

            if not row_index:
                raise SheetsError(f"Group not found: {chat_id}")

            current = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A{row_index}:L{row_index}"
            )

            if not current or not current[0]:
                raise SheetsError(f"Failed to read group data: {chat_id}")

            row = current[0]

            while len(row) < 12:
                row.append("")

            field_index = {
                "name": 1,
                "spreadsheet_id": 2,
                "spreadsheet_url": 3,
                "status": 4,
                "admin_user_id": 5,
                "admin_username": 6,
                "member_count": 9,
                "transaction_count": 10,
                "notes": 11
            }

            for field, value in updates.items():
                if field in field_index:
                    row[field_index[field]] = str(value)

            row[8] = datetime.now().isoformat()

            await self.sheets_client.write_range(
                self.spreadsheet_id,
                f"{self.SHEET_GROUPS}!A{row_index}:L{row_index}",
                [row]
            )

            group_data = self._row_to_group_dict(row)
            self._groups_cache[chat_id] = group_data

            await self.sheets_client.set_group_config(chat_id, group_data)

            return group_data

        except Exception as e:
            logger.error(f"Error updating group: {e}")
            raise SheetsError(f"Failed to update group: {e}")

    async def activate_group(self, chat_id: int) -> Dict[str, Any]:
        """Activate a group."""
        return await self.update_group(chat_id, status="active")

    async def deactivate_group(self, chat_id: int) -> Dict[str, Any]:
        """Deactivate a group."""
        return await self.update_group(chat_id, status="inactive")

    async def get_super_admins(self) -> List[Dict[str, Any]]:
        """Get all super admins."""
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_SUPER_ADMINS}!A:E"
            )

            admins = []
            for row in values[1:]:
                if len(row) >= 2:
                    admins.append({
                        "user_id": int(row[0]) if row[0] else 0,
                        "username": row[1] if len(row) > 1 else "",
                        "added_at": row[2] if len(row) > 2 else "",
                        "added_by": row[3] if len(row) > 3 else "",
                        "status": row[4] if len(row) > 4 else "active"
                    })

            return admins

        except Exception as e:
            logger.error(f"Error getting super admins: {e}")
            return []

    async def add_super_admin(
        self,
        user_id: int,
        username: str,
        added_by: str = "system"
    ) -> None:
        """Add a super admin."""
        row = [
            str(user_id),
            username,
            datetime.now().isoformat(),
            added_by,
            "active"
        ]

        await self.sheets_client.append_rows(
            self.spreadsheet_id,
            f"{self.SHEET_SUPER_ADMINS}!A:E",
            [row]
        )

    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        try:
            groups = await self.get_all_groups()

            active_groups = [g for g in groups if g.get("status") == "active"]

            total_transactions = sum(
                int(g.get("transaction_count", 0)) for g in groups
            )

            return {
                "total_groups": len(groups),
                "active_groups": len(active_groups),
                "total_transactions": total_transactions,
                "total_volume": 0
            }

        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            return {
                "total_groups": 0,
                "active_groups": 0,
                "total_transactions": 0,
                "total_volume": 0
            }

    async def log_event(
        self,
        event_type: str,
        message: str,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> None:
        """Log an event to the logs sheet."""
        row = [
            datetime.now().isoformat(),
            event_type,
            message,
            str(chat_id) if chat_id else "",
            str(user_id) if user_id else ""
        ]

        try:
            await self.sheets_client.append_rows(
                self.spreadsheet_id,
                f"{self.SHEET_LOGS}!A:E",
                [row]
            )
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def _row_to_group_dict(self, row: List[str]) -> Dict[str, Any]:
        """Convert a row to a group dictionary."""
        return {
            "chat_id": int(row[0]) if row[0] else 0,
            "name": row[1] if len(row) > 1 else "",
            "spreadsheet_id": row[2] if len(row) > 2 else "",
            "spreadsheet_url": row[3] if len(row) > 3 else "",
            "status": row[4] if len(row) > 4 else "pending",
            "admin_user_id": int(row[5]) if len(row) > 5 and row[5] else 0,
            "admin_username": row[6] if len(row) > 6 else "",
            "created_at": row[7] if len(row) > 7 else "",
            "updated_at": row[8] if len(row) > 8 else "",
            "member_count": int(row[9]) if len(row) > 9 and row[9] else 0,
            "transaction_count": int(row[10]) if len(row) > 10 and row[10] else 0,
            "notes": row[11] if len(row) > 11 else ""
        }

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self._cache_timestamp:
            return False

        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds

    def invalidate_cache(self, chat_id: Optional[int] = None) -> None:
        """Invalidate cache."""
        if chat_id:
            self._groups_cache.pop(chat_id, None)
        else:
            self._groups_cache.clear()
            self._cache_timestamp = None
