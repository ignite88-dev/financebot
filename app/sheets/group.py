# path: app/sheets/group.py
"""
Group sheet - Manages individual group spreadsheets.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from app.sheets.client import SheetsClient
from app.sheets.schema import SheetSchema
from app.infra.logger import get_logger
from app.infra.exceptions import SheetsError


logger = get_logger(__name__)


class GroupSheet:
    """
    Manages an individual group's spreadsheet.

    Each group spreadsheet contains:
    - CONFIG: Group configuration
    - USERS: Member data
    - TRANSACTIONS: Financial transactions
    - JOURNAL: Notes and entries
    - AI_MEMORY: AI conversation context
    - AUDIT_LOG: Activity audit trail
    """

    SHEET_CONFIG = "CONFIG"
    SHEET_USERS = "USERS"
    SHEET_TRANSACTIONS = "TRANSACTIONS"
    SHEET_JOURNAL = "JOURNAL"
    SHEET_AI_MEMORY = "AI_MEMORY"
    SHEET_AUDIT_LOG = "AUDIT_LOG"

    TRANSACTION_HEADERS = [
        "id", "timestamp", "type", "amount", "description",
        "category", "user_id", "username", "balance_after", "notes"
    ]

    def __init__(
        self,
        sheets_client: SheetsClient,
        spreadsheet_id: str
    ):
        self.sheets_client = sheets_client
        self.spreadsheet_id = spreadsheet_id

        self._balance_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None

    async def initialize(self) -> None:
        """Initialize the group spreadsheet with required sheets."""
        logger.info(f"Initializing group sheet: {self.spreadsheet_id}")

        try:
            info = await self.sheets_client.get_spreadsheet_info(
                self.spreadsheet_id
            )

            existing_sheets = info.get("sheets", [])

            required_sheets = {
                self.SHEET_CONFIG: self._get_config_headers(),
                self.SHEET_USERS: self._get_users_headers(),
                self.SHEET_TRANSACTIONS: self.TRANSACTION_HEADERS,
                self.SHEET_JOURNAL: self._get_journal_headers(),
                self.SHEET_AI_MEMORY: self._get_memory_headers(),
                self.SHEET_AUDIT_LOG: self._get_audit_headers()
            }

            for sheet_name, headers in required_sheets.items():
                if sheet_name not in existing_sheets:
                    await self.sheets_client.add_sheet(
                        self.spreadsheet_id,
                        sheet_name
                    )

                await self.sheets_client.write_range(
                    self.spreadsheet_id,
                    f"{sheet_name}!A1:{chr(64 + len(headers))}1",
                    [headers]
                )

            logger.info("Group sheet initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize group sheet: {e}")
            raise SheetsError(f"Group sheet initialization failed: {e}")

    def _get_config_headers(self) -> List[str]:
        return ["key", "value", "description", "updated_at"]

    def _get_users_headers(self) -> List[str]:
        return [
            "user_id", "username", "first_seen", "last_active",
            "message_count", "transaction_count", "role"
        ]

    def _get_journal_headers(self) -> List[str]:
        return ["id", "timestamp", "type", "content", "user_id", "username"]

    def _get_memory_headers(self) -> List[str]:
        return [
            "id", "timestamp", "user_id", "username",
            "message", "intent", "response", "embedding_id"
        ]

    def _get_audit_headers(self) -> List[str]:
        return [
            "timestamp", "action", "user_id", "username",
            "details", "ip_address"
        ]

    async def add_transaction(
        self,
        tx_type: str,
        amount: float,
        description: str,
        user_id: int,
        username: str,
        category: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Add a new transaction.

        Args:
            tx_type: Transaction type (income/expense)
            amount: Transaction amount
            description: Transaction description
            user_id: User who made the transaction
            username: Username
            category: Optional category
            notes: Optional notes

        Returns:
            The created transaction data
        """
        logger.info(f"Adding transaction: {tx_type} {amount} by {username}")

        tx_id = f"TX{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"

        current_balance = await self._get_current_balance()
        if tx_type == "income":
            new_balance = current_balance + amount
        else:
            new_balance = current_balance - amount

        row = [
            tx_id,
            datetime.now().isoformat(),
            tx_type,
            str(amount),
            description,
            category,
            str(user_id),
            username,
            str(new_balance),
            notes
        ]

        try:
            await self.sheets_client.append_rows(
                self.spreadsheet_id,
                f"{self.SHEET_TRANSACTIONS}!A:J",
                [row]
            )

            self._invalidate_balance_cache()

            await self._log_audit(
                action="transaction_added",
                user_id=user_id,
                username=username,
                details=f"{tx_type}: {amount} - {description}"
            )

            await self._update_user_transaction_count(user_id, username)

            return {
                "id": tx_id,
                "timestamp": row[1],
                "type": tx_type,
                "amount": amount,
                "description": description,
                "balance_after": new_balance
            }

        except Exception as e:
            logger.error(f"Error adding transaction: {e}")
            raise SheetsError(f"Failed to add transaction: {e}")

    async def get_transactions(
        self,
        limit: Optional[int] = None,
        tx_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transactions with optional filters.

        Args:
            limit: Maximum number of transactions
            tx_type: Filter by type (income/expense)
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of transaction dicts
        """
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_TRANSACTIONS}!A:J"
            )

            transactions = []
            for row in values[1:]:
                if len(row) < 5:
                    continue

                tx = self._row_to_transaction_dict(row)

                if tx_type and tx["type"] != tx_type:
                    continue

                if start_date:
                    tx_date = datetime.fromisoformat(tx["timestamp"])
                    if tx_date < start_date:
                        continue

                if end_date:
                    tx_date = datetime.fromisoformat(tx["timestamp"])
                    if tx_date > end_date:
                        continue

                transactions.append(tx)

            transactions.reverse()

            if limit:
                transactions = transactions[:limit]

            return transactions

        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            return []

    async def get_recent_transactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent transactions."""
        return await self.get_transactions(limit=limit)

    async def get_balance(self) -> Dict[str, Any]:
        """
        Get current balance and totals.

        Returns:
            Dict with total_income, total_expense, and balance
        """
        if self._is_balance_cache_valid():
            return self._balance_cache

        try:
            transactions = await self.get_transactions()

            total_income = sum(
                tx["amount"] for tx in transactions
                if tx["type"] == "income"
            )

            total_expense = sum(
                tx["amount"] for tx in transactions
                if tx["type"] == "expense"
            )

            balance = total_income - total_expense

            self._balance_cache = {
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": balance,
                "transaction_count": len(transactions)
            }
            self._cache_timestamp = datetime.now()

            return self._balance_cache

        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {
                "total_income": 0,
                "total_expense": 0,
                "balance": 0,
                "transaction_count": 0
            }

    async def get_report(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a financial report for a period.

        Args:
            start_date: Report start date
            end_date: Report end date (defaults to now)

        Returns:
            Report data dict
        """
        if not end_date:
            end_date = datetime.now()

        try:
            transactions = await self.get_transactions(
                start_date=start_date,
                end_date=end_date
            )

            income_txs = [tx for tx in transactions if tx["type"] == "income"]
            expense_txs = [tx for tx in transactions if tx["type"] == "expense"]

            total_income = sum(tx["amount"] for tx in income_txs)
            total_expense = sum(tx["amount"] for tx in expense_txs)

            expense_txs_sorted = sorted(
                expense_txs,
                key=lambda x: x["amount"],
                reverse=True
            )

            category_totals = {}
            for tx in transactions:
                cat = tx.get("category") or "Uncategorized"
                if cat not in category_totals:
                    category_totals[cat] = {"income": 0, "expense": 0}
                category_totals[cat][tx["type"]] += tx["amount"]

            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": total_income - total_expense,
                "income_count": len(income_txs),
                "expense_count": len(expense_txs),
                "top_expenses": expense_txs_sorted[:5],
                "category_breakdown": category_totals,
                "transaction_count": len(transactions)
            }

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {
                "total_income": 0,
                "total_expense": 0,
                "balance": 0,
                "income_count": 0,
                "expense_count": 0,
                "top_expenses": [],
                "category_breakdown": {},
                "transaction_count": 0
            }

    async def add_memory_entry(
        self,
        user_id: int,
        username: str,
        message: str,
        intent: Optional[str] = None,
        response: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Add an entry to AI memory."""
        if not timestamp:
            timestamp = datetime.now()

        entry_id = f"MEM{timestamp.strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4]}"

        row = [
            entry_id,
            timestamp.isoformat(),
            str(user_id),
            username,
            message,
            intent or "",
            response or "",
            ""
        ]

        try:
            await self.sheets_client.append_rows(
                self.spreadsheet_id,
                f"{self.SHEET_AI_MEMORY}!A:H",
                [row]
            )
        except Exception as e:
            logger.error(f"Error adding memory entry: {e}")

    async def get_memory_entries(
        self,
        limit: int = 50,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get AI memory entries."""
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_AI_MEMORY}!A:H"
            )

            entries = []
            for row in values[1:]:
                if len(row) < 5:
                    continue

                entry = {
                    "id": row[0],
                    "timestamp": row[1],
                    "user_id": int(row[2]) if row[2] else 0,
                    "username": row[3],
                    "message": row[4],
                    "intent": row[5] if len(row) > 5 else "",
                    "response": row[6] if len(row) > 6 else ""
                }

                if user_id and entry["user_id"] != user_id:
                    continue

                entries.append(entry)

            entries.reverse()
            return entries[:limit]

        except Exception as e:
            logger.error(f"Error getting memory entries: {e}")
            return []

    async def add_user(
        self,
        user_id: int,
        username: str,
        role: str = "member"
    ) -> None:
        """Add or update a user."""
        try:
            row_index = await self.sheets_client.find_row(
                self.spreadsheet_id,
                self.SHEET_USERS,
                0,
                str(user_id)
            )

            now = datetime.now().isoformat()

            if row_index:
                await self.sheets_client.write_range(
                    self.spreadsheet_id,
                    f"{self.SHEET_USERS}!D{row_index}",
                    [[now]]
                )
            else:
                row = [
                    str(user_id),
                    username,
                    now,
                    now,
                    "0",
                    "0",
                    role
                ]
                await self.sheets_client.append_rows(
                    self.spreadsheet_id,
                    f"{self.SHEET_USERS}!A:G",
                    [row]
                )

        except Exception as e:
            logger.error(f"Error adding user: {e}")

    async def get_config(self, key: str) -> Optional[str]:
        """Get a config value."""
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_CONFIG}!A:B"
            )

            for row in values[1:]:
                if len(row) >= 2 and row[0] == key:
                    return row[1]

            return None

        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return None

    async def set_config(self, key: str, value: str, description: str = "") -> None:
        """Set a config value."""
        try:
            row_index = await self.sheets_client.find_row(
                self.spreadsheet_id,
                self.SHEET_CONFIG,
                0,
                key
            )

            now = datetime.now().isoformat()

            if row_index:
                await self.sheets_client.write_range(
                    self.spreadsheet_id,
                    f"{self.SHEET_CONFIG}!B{row_index}:D{row_index}",
                    [[value, description, now]]
                )
            else:
                row = [key, value, description, now]
                await self.sheets_client.append_rows(
                    self.spreadsheet_id,
                    f"{self.SHEET_CONFIG}!A:D",
                    [row]
                )

        except Exception as e:
            logger.error(f"Error setting config: {e}")

    async def _get_current_balance(self) -> float:
        """Get current balance from last transaction."""
        try:
            values = await self.sheets_client.read_range(
                self.spreadsheet_id,
                f"{self.SHEET_TRANSACTIONS}!I:I"
            )

            if len(values) > 1:
                last_balance = values[-1][0] if values[-1] else "0"
                return float(last_balance)

            return 0.0

        except Exception as e:
            logger.error(f"Error getting current balance: {e}")
            return 0.0

    async def _log_audit(
        self,
        action: str,
        user_id: int,
        username: str,
        details: str
    ) -> None:
        """Log an audit entry."""
        row = [
            datetime.now().isoformat(),
            action,
            str(user_id),
            username,
            details,
            ""
        ]

        try:
            await self.sheets_client.append_rows(
                self.spreadsheet_id,
                f"{self.SHEET_AUDIT_LOG}!A:F",
                [row]
            )
        except Exception as e:
            logger.error(f"Error logging audit: {e}")

    async def _update_user_transaction_count(
        self,
        user_id: int,
        username: str
    ) -> None:
        """Update user's transaction count."""
        try:
            row_index = await self.sheets_client.find_row(
                self.spreadsheet_id,
                self.SHEET_USERS,
                0,
                str(user_id)
            )

            if row_index:
                values = await self.sheets_client.read_range(
                    self.spreadsheet_id,
                    f"{self.SHEET_USERS}!F{row_index}"
                )

                current_count = int(values[0][0]) if values and values[0] else 0
                new_count = current_count + 1

                await self.sheets_client.write_range(
                    self.spreadsheet_id,
                    f"{self.SHEET_USERS}!F{row_index}",
                    [[str(new_count)]]
                )
            else:
                await self.add_user(user_id, username)

        except Exception as e:
            logger.error(f"Error updating user transaction count: {e}")

    def _row_to_transaction_dict(self, row: List[str]) -> Dict[str, Any]:
        """Convert row to transaction dict."""
        return {
            "id": row[0] if row[0] else "",
            "timestamp": row[1] if len(row) > 1 else "",
            "type": row[2] if len(row) > 2 else "",
            "amount": float(row[3]) if len(row) > 3 and row[3] else 0,
            "description": row[4] if len(row) > 4 else "",
            "category": row[5] if len(row) > 5 else "",
            "user_id": int(row[6]) if len(row) > 6 and row[6] else 0,
            "username": row[7] if len(row) > 7 else "",
            "balance_after": float(row[8]) if len(row) > 8 and row[8] else 0,
            "notes": row[9] if len(row) > 9 else ""
        }

    def _is_balance_cache_valid(self) -> bool:
        """Check if balance cache is valid."""
        if not self._balance_cache or not self._cache_timestamp:
            return False

        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < 30

    def _invalidate_balance_cache(self) -> None:
        """Invalidate balance cache."""
        self._balance_cache = None
        self._cache_timestamp = None
