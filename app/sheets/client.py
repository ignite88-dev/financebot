# path: app/sheets/client.py
"""
Google Sheets client - Core client for interacting with Google Sheets API.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.infra.logger import get_logger
from app.infra.exceptions import SheetsError, SheetNotFoundError


logger = get_logger(__name__)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


class SheetsClient:
    """
    Client for Google Sheets API operations.

    Provides async-compatible methods for reading and writing to spreadsheets.
    """

    def __init__(
        self,
        credentials_path: str,
        service_account_email: str
    ):
        self.credentials_path = credentials_path
        self.service_account_email = service_account_email

        self._credentials: Optional[Credentials] = None
        self._sheets_service = None
        self._drive_service = None
        self._loop = None

        self._group_config_cache: Dict[int, Dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Initialize the Google API clients."""
        logger.info("Initializing Google Sheets client...")

        try:
            self._credentials = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=SCOPES
            )

            self._sheets_service = build(
                "sheets", "v4",
                credentials=self._credentials,
                cache_discovery=False
            )

            self._drive_service = build(
                "drive", "v3",
                credentials=self._credentials,
                cache_discovery=False
            )

            self._loop = asyncio.get_event_loop()

            logger.info("Google Sheets client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Sheets client: {e}")
            raise SheetsError(f"Sheets initialization failed: {e}")

    async def close(self) -> None:
        """Close the client connections."""
        logger.info("Closing Sheets client")

    async def _run_in_executor(self, func, *args, **kwargs):
        """Run a blocking function in an executor."""
        return await self._loop.run_in_executor(
            None,
            lambda: func(*args, **kwargs)
        )

    async def create_spreadsheet(
        self,
        title: str,
        sheet_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new spreadsheet.

        Args:
            title: The spreadsheet title
            sheet_names: List of sheet names to create

        Returns:
            Dict with spreadsheet_id and url
        """
        logger.info(f"Creating spreadsheet: {title}")

        sheets = [{"properties": {"title": "Sheet1"}}]
        if sheet_names:
            sheets = [
                {"properties": {"title": name}}
                for name in sheet_names
            ]

        spreadsheet_body = {
            "properties": {"title": title},
            "sheets": sheets
        }

        try:
            def create():
                return self._sheets_service.spreadsheets().create(
                    body=spreadsheet_body
                ).execute()

            result = await self._run_in_executor(create)

            spreadsheet_id = result["spreadsheetId"]
            url = result["spreadsheetUrl"]

            logger.info(f"Created spreadsheet: {spreadsheet_id}")

            return {
                "spreadsheet_id": spreadsheet_id,
                "url": url
            }

        except HttpError as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            raise SheetsError(f"Failed to create spreadsheet: {e}")

    async def share_spreadsheet(
        self,
        spreadsheet_id: str,
        email: str,
        role: str = "writer"
    ) -> None:
        """
        Share a spreadsheet with an email address.

        Args:
            spreadsheet_id: The spreadsheet ID
            email: Email to share with
            role: Permission role (reader, writer, owner)
        """
        logger.info(f"Sharing spreadsheet {spreadsheet_id} with {email}")

        permission = {
            "type": "user",
            "role": role,
            "emailAddress": email
        }

        try:
            def share():
                return self._drive_service.permissions().create(
                    fileId=spreadsheet_id,
                    body=permission,
                    sendNotificationEmail=False
                ).execute()

            await self._run_in_executor(share)

            logger.info(f"Shared spreadsheet with {email}")

        except HttpError as e:
            logger.error(f"Failed to share spreadsheet: {e}")
            raise SheetsError(f"Failed to share spreadsheet: {e}")

    async def get_spreadsheet_info(
        self,
        spreadsheet_id: str
    ) -> Dict[str, Any]:
        """Get spreadsheet metadata."""
        try:
            def get_info():
                return self._sheets_service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id
                ).execute()

            result = await self._run_in_executor(get_info)

            return {
                "spreadsheet_id": result["spreadsheetId"],
                "title": result["properties"]["title"],
                "url": result["spreadsheetUrl"],
                "sheets": [
                    s["properties"]["title"]
                    for s in result.get("sheets", [])
                ]
            }

        except HttpError as e:
            if e.resp.status == 404:
                raise SheetNotFoundError(f"Spreadsheet not found: {spreadsheet_id}")
            raise SheetsError(f"Failed to get spreadsheet info: {e}")

    async def read_range(
        self,
        spreadsheet_id: str,
        range_name: str
    ) -> List[List[Any]]:
        """
        Read a range of cells from a spreadsheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: The A1 notation range (e.g., "Sheet1!A1:D10")

        Returns:
            List of rows, where each row is a list of cell values
        """
        try:
            def read():
                return self._sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name
                ).execute()

            result = await self._run_in_executor(read)

            return result.get("values", [])

        except HttpError as e:
            if e.resp.status == 404:
                raise SheetNotFoundError(f"Range not found: {range_name}")
            raise SheetsError(f"Failed to read range: {e}")

    async def write_range(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Write values to a range of cells.

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: The A1 notation range
            values: 2D list of values to write
            value_input_option: How to interpret the values

        Returns:
            Update result with updatedCells count
        """
        body = {"values": values}

        try:
            def write():
                return self._sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body=body
                ).execute()

            result = await self._run_in_executor(write)

            return {
                "updated_cells": result.get("updatedCells", 0),
                "updated_range": result.get("updatedRange", "")
            }

        except HttpError as e:
            raise SheetsError(f"Failed to write range: {e}")

    async def append_rows(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> Dict[str, Any]:
        """
        Append rows to a sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range_name: The sheet name or range
            values: 2D list of values to append

        Returns:
            Append result with updates info
        """
        body = {"values": values}

        try:
            def append():
                return self._sheets_service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    insertDataOption="INSERT_ROWS",
                    body=body
                ).execute()

            result = await self._run_in_executor(append)

            return {
                "updated_range": result.get("updates", {}).get("updatedRange", ""),
                "updated_rows": result.get("updates", {}).get("updatedRows", 0)
            }

        except HttpError as e:
            raise SheetsError(f"Failed to append rows: {e}")

    async def add_sheet(
        self,
        spreadsheet_id: str,
        sheet_title: str
    ) -> int:
        """
        Add a new sheet to a spreadsheet.

        Returns:
            The new sheet's ID
        """
        request = {
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": sheet_title
                    }
                }
            }]
        }

        try:
            def add():
                return self._sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=request
                ).execute()

            result = await self._run_in_executor(add)

            sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
            return sheet_id

        except HttpError as e:
            raise SheetsError(f"Failed to add sheet: {e}")

    async def batch_update(
        self,
        spreadsheet_id: str,
        requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a batch update on a spreadsheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            requests: List of update requests

        Returns:
            Batch update result
        """
        body = {"requests": requests}

        try:
            def batch():
                return self._sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()

            result = await self._run_in_executor(batch)

            return result

        except HttpError as e:
            raise SheetsError(f"Batch update failed: {e}")

    async def find_row(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        column_index: int,
        search_value: str
    ) -> Optional[int]:
        """
        Find a row by matching a column value.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: The sheet name
            column_index: Column index to search (0-based)
            search_value: Value to find

        Returns:
            Row index (1-based) or None if not found
        """
        try:
            values = await self.read_range(
                spreadsheet_id,
                f"{sheet_name}!A:Z"
            )

            for i, row in enumerate(values):
                if len(row) > column_index and str(row[column_index]) == str(search_value):
                    return i + 1

            return None

        except Exception as e:
            logger.error(f"Error finding row: {e}")
            return None

    async def get_group_config(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get group configuration from cache or master sheet."""
        if chat_id in self._group_config_cache:
            return self._group_config_cache[chat_id]

        return None

    async def set_group_config(self, chat_id: int, config: Dict[str, Any]) -> None:
        """Cache group configuration."""
        self._group_config_cache[chat_id] = config

    async def get_user_profile(
        self,
        chat_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get user profile from group sheet."""
        config = await self.get_group_config(chat_id)
        if not config or not config.get("spreadsheet_id"):
            return None

        try:
            row_index = await self.find_row(
                config["spreadsheet_id"],
                "USERS",
                0,
                str(user_id)
            )

            if row_index:
                values = await self.read_range(
                    config["spreadsheet_id"],
                    f"USERS!A{row_index}:G{row_index}"
                )

                if values and values[0]:
                    row = values[0]
                    return {
                        "user_id": int(row[0]) if row[0] else 0,
                        "username": row[1] if len(row) > 1 else "",
                        "first_seen": row[2] if len(row) > 2 else "",
                        "last_active": row[3] if len(row) > 3 else "",
                        "message_count": int(row[4]) if len(row) > 4 and row[4] else 0,
                        "transaction_count": int(row[5]) if len(row) > 5 and row[5] else 0,
                        "role": row[6] if len(row) > 6 else "member"
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
