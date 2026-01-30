# path: app/admin/panel.py
"""
Admin Panel - Central admin management interface.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.infra.logger import get_logger


logger = get_logger(__name__)


class AdminPanel:
    """
    Admin panel for managing all groups and system settings.
    """

    def __init__(
        self,
        sheets_client: SheetsClient,
        master_sheet: MasterSheet
    ):
        self.sheets_client = sheets_client
        self.master_sheet = master_sheet

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get system-wide statistics.

        Returns:
            Statistics dictionary
        """
        try:
            stats = await self.master_sheet.get_stats()

            return {
                "total_groups": stats.get("total_groups", 0),
                "active_groups": stats.get("active_groups", 0),
                "total_transactions": stats.get("total_transactions", 0),
                "total_users": stats.get("total_users", 0),
                "super_admins": stats.get("super_admins", 0),
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "total_groups": 0,
                "active_groups": 0,
                "total_transactions": 0,
                "total_users": 0,
                "error": str(e)
            }

    async def get_groups_list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of registered groups.

        Args:
            status: Filter by status
            limit: Maximum groups to return
            offset: Pagination offset

        Returns:
            List of group data
        """
        try:
            groups = await self.master_sheet.get_all_groups(status=status)

            groups = groups[offset:offset + limit]

            return [
                {
                    "chat_id": g.get("chat_id"),
                    "chat_title": g.get("chat_title"),
                    "status": g.get("status"),
                    "admin_username": g.get("admin_username"),
                    "created_at": g.get("created_at"),
                    "last_active": g.get("last_active"),
                    "transaction_count": g.get("transaction_count", 0)
                }
                for g in groups
            ]

        except Exception as e:
            logger.error(f"Error getting groups: {e}")
            return []

    async def get_group_details(
        self,
        chat_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a group.

        Args:
            chat_id: The chat ID

        Returns:
            Group details or None
        """
        try:
            group = await self.master_sheet.get_group(chat_id)
            if not group:
                return None

            return {
                "chat_id": group.get("chat_id"),
                "chat_title": group.get("chat_title"),
                "spreadsheet_id": group.get("spreadsheet_id"),
                "spreadsheet_url": group.get("spreadsheet_url"),
                "admin_user_id": group.get("admin_user_id"),
                "admin_username": group.get("admin_username"),
                "status": group.get("status"),
                "created_at": group.get("created_at"),
                "last_active": group.get("last_active"),
                "member_count": group.get("member_count", 0),
                "transaction_count": group.get("transaction_count", 0)
            }

        except Exception as e:
            logger.error(f"Error getting group details: {e}")
            return None

    async def suspend_group(
        self,
        chat_id: int,
        reason: str = ""
    ) -> bool:
        """
        Suspend a group.

        Args:
            chat_id: The chat ID
            reason: Suspension reason

        Returns:
            True if successful
        """
        try:
            await self.master_sheet.update_group_status(chat_id, "suspended")

            await self.master_sheet.log_system_event(
                level="WARNING",
                source="admin_panel",
                message=f"Group suspended: {reason}",
                chat_id=chat_id
            )

            logger.info(f"Suspended group {chat_id}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error suspending group: {e}")
            return False

    async def reactivate_group(
        self,
        chat_id: int
    ) -> bool:
        """
        Reactivate a suspended group.

        Args:
            chat_id: The chat ID

        Returns:
            True if successful
        """
        try:
            await self.master_sheet.update_group_status(chat_id, "active")

            await self.master_sheet.log_system_event(
                level="INFO",
                source="admin_panel",
                message="Group reactivated",
                chat_id=chat_id
            )

            logger.info(f"Reactivated group {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Error reactivating group: {e}")
            return False

    async def delete_group(
        self,
        chat_id: int
    ) -> bool:
        """
        Delete a group (mark as inactive).

        Args:
            chat_id: The chat ID

        Returns:
            True if successful
        """
        try:
            result = await self.master_sheet.delete_group(chat_id)

            if result:
                await self.master_sheet.log_system_event(
                    level="WARNING",
                    source="admin_panel",
                    message="Group deleted",
                    chat_id=chat_id
                )

            return result

        except Exception as e:
            logger.error(f"Error deleting group: {e}")
            return False

    async def get_super_admins(self) -> List[Dict[str, Any]]:
        """
        Get list of super admins.

        Returns:
            List of super admin data
        """
        try:
            values = await self.sheets_client.read_range(
                self.master_sheet.spreadsheet_id,
                "SUPER_ADMINS!A:E"
            )

            admins = []
            for row in values[1:]:
                if len(row) >= 2:
                    admins.append({
                        "user_id": int(row[0]) if row[0] else 0,
                        "username": row[1] if len(row) > 1 else "",
                        "added_at": row[2] if len(row) > 2 else "",
                        "added_by": row[3] if len(row) > 3 else "",
                        "permissions": row[4] if len(row) > 4 else "all"
                    })

            return admins

        except Exception as e:
            logger.error(f"Error getting super admins: {e}")
            return []

    async def add_super_admin(
        self,
        user_id: int,
        username: str,
        added_by: str
    ) -> bool:
        """
        Add a new super admin.

        Args:
            user_id: User ID to add
            username: Username
            added_by: Who added this admin

        Returns:
            True if successful
        """
        try:
            await self.master_sheet.add_super_admin(
                user_id=user_id,
                username=username,
                added_by=added_by
            )

            await self.master_sheet.log_system_event(
                level="INFO",
                source="admin_panel",
                message=f"Super admin added: {username}",
                user_id=user_id
            )

            return True

        except Exception as e:
            logger.error(f"Error adding super admin: {e}")
            return False

    async def get_system_logs(
        self,
        limit: int = 50,
        level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get system logs.

        Args:
            limit: Maximum logs to return
            level: Filter by log level

        Returns:
            List of log entries
        """
        try:
            values = await self.sheets_client.read_range(
                self.master_sheet.spreadsheet_id,
                "SYSTEM_LOG!A:G"
            )

            logs = []
            for row in values[1:]:
                if len(row) >= 4:
                    log_entry = {
                        "timestamp": row[0],
                        "level": row[1] if len(row) > 1 else "",
                        "source": row[2] if len(row) > 2 else "",
                        "message": row[3] if len(row) > 3 else "",
                        "chat_id": row[4] if len(row) > 4 else "",
                        "user_id": row[5] if len(row) > 5 else "",
                        "details": row[6] if len(row) > 6 else ""
                    }

                    if level and log_entry["level"] != level:
                        continue

                    logs.append(log_entry)

            logs.reverse()
            return logs[:limit]

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return []

    async def get_global_settings(self) -> Dict[str, str]:
        """
        Get all global settings.

        Returns:
            Settings dictionary
        """
        try:
            values = await self.sheets_client.read_range(
                self.master_sheet.spreadsheet_id,
                "GLOBAL_SETTINGS!A:B"
            )

            settings = {}
            for row in values[1:]:
                if len(row) >= 2:
                    settings[row[0]] = row[1]

            return settings

        except Exception as e:
            logger.error(f"Error getting settings: {e}")
            return {}

    async def update_global_setting(
        self,
        key: str,
        value: str
    ) -> bool:
        """
        Update a global setting.

        Args:
            key: Setting key
            value: New value

        Returns:
            True if successful
        """
        try:
            await self.master_sheet.set_setting(key, value)

            await self.master_sheet.log_system_event(
                level="INFO",
                source="admin_panel",
                message=f"Setting updated: {key}={value}"
            )

            return True

        except Exception as e:
            logger.error(f"Error updating setting: {e}")
            return False

    async def get_inactive_groups(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get groups that have been inactive.

        Args:
            days: Number of days of inactivity

        Returns:
            List of inactive groups
        """
        try:
            all_groups = await self.master_sheet.get_all_groups(status="active")

            cutoff = datetime.now() - timedelta(days=days)
            inactive = []

            for group in all_groups:
                last_active = group.get("last_active")
                if last_active:
                    try:
                        last_active_dt = datetime.fromisoformat(last_active)
                        if last_active_dt < cutoff:
                            group["inactive_days"] = (datetime.now() - last_active_dt).days
                            inactive.append(group)
                    except ValueError:
                        pass

            inactive.sort(key=lambda x: x.get("inactive_days", 0), reverse=True)
            return inactive

        except Exception as e:
            logger.error(f"Error getting inactive groups: {e}")
            return []

    async def broadcast_message(
        self,
        message: str,
        target_groups: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Broadcast a message to groups.

        Note: This returns the broadcast info, actual sending should be
        done by the bot client.

        Args:
            message: Message to broadcast
            target_groups: Specific groups to target (None = all active)

        Returns:
            Broadcast information
        """
        try:
            if target_groups:
                groups = [
                    await self.master_sheet.get_group(chat_id)
                    for chat_id in target_groups
                ]
                groups = [g for g in groups if g]
            else:
                groups = await self.master_sheet.get_all_groups(status="active")

            await self.master_sheet.log_system_event(
                level="INFO",
                source="admin_panel",
                message=f"Broadcast to {len(groups)} groups",
                details=message[:100]
            )

            return {
                "target_count": len(groups),
                "target_ids": [g["chat_id"] for g in groups],
                "message": message,
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error preparing broadcast: {e}")
            return {"error": str(e)}
