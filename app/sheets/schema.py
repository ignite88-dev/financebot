# path: app/sheets/schema.py
"""
Schema definitions for spreadsheet structure validation.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ColumnType(Enum):
    """Column data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    CURRENCY = "currency"


@dataclass
class ColumnSchema:
    """Schema definition for a column."""
    name: str
    display_name: str
    column_type: ColumnType
    required: bool = False
    default: Optional[str] = None
    validation: Optional[str] = None
    description: str = ""


@dataclass
class SheetSchema:
    """Schema definition for a sheet."""
    name: str
    display_name: str
    columns: List[ColumnSchema] = field(default_factory=list)
    primary_key: Optional[str] = None
    description: str = ""

    def get_headers(self) -> List[str]:
        """Get column headers."""
        return [col.name for col in self.columns]

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        """Get column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def validate_row(self, row: List[str]) -> Dict[str, Any]:
        """
        Validate a row against the schema.

        Args:
            row: List of cell values

        Returns:
            Validation result with errors if any
        """
        result = {"valid": True, "errors": []}

        for i, col in enumerate(self.columns):
            value = row[i] if i < len(row) else ""

            if col.required and not value:
                result["valid"] = False
                result["errors"].append(f"Column '{col.name}' is required")

            if value and col.column_type == ColumnType.INTEGER:
                try:
                    int(value)
                except ValueError:
                    result["valid"] = False
                    result["errors"].append(
                        f"Column '{col.name}' must be an integer"
                    )

            if value and col.column_type == ColumnType.FLOAT:
                try:
                    float(value)
                except ValueError:
                    result["valid"] = False
                    result["errors"].append(
                        f"Column '{col.name}' must be a number"
                    )

        return result


class SchemaRegistry:
    """Registry of all sheet schemas."""

    _schemas: Dict[str, SheetSchema] = {}

    @classmethod
    def register(cls, schema: SheetSchema) -> None:
        """Register a schema."""
        cls._schemas[schema.name] = schema

    @classmethod
    def get(cls, name: str) -> Optional[SheetSchema]:
        """Get a schema by name."""
        return cls._schemas.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, SheetSchema]:
        """Get all schemas."""
        return cls._schemas.copy()


TRANSACTIONS_SCHEMA = SheetSchema(
    name="TRANSACTIONS",
    display_name="Transaksi",
    description="Catatan transaksi keuangan grup",
    primary_key="id",
    columns=[
        ColumnSchema(
            name="id",
            display_name="ID",
            column_type=ColumnType.STRING,
            required=True,
            description="ID unik transaksi"
        ),
        ColumnSchema(
            name="timestamp",
            display_name="Waktu",
            column_type=ColumnType.DATETIME,
            required=True,
            description="Waktu transaksi"
        ),
        ColumnSchema(
            name="type",
            display_name="Tipe",
            column_type=ColumnType.STRING,
            required=True,
            validation="income|expense",
            description="Tipe transaksi (income/expense)"
        ),
        ColumnSchema(
            name="amount",
            display_name="Jumlah",
            column_type=ColumnType.CURRENCY,
            required=True,
            description="Jumlah transaksi"
        ),
        ColumnSchema(
            name="description",
            display_name="Keterangan",
            column_type=ColumnType.STRING,
            required=True,
            description="Deskripsi transaksi"
        ),
        ColumnSchema(
            name="category",
            display_name="Kategori",
            column_type=ColumnType.STRING,
            required=False,
            description="Kategori transaksi"
        ),
        ColumnSchema(
            name="user_id",
            display_name="User ID",
            column_type=ColumnType.INTEGER,
            required=True,
            description="ID user yang melakukan transaksi"
        ),
        ColumnSchema(
            name="username",
            display_name="Username",
            column_type=ColumnType.STRING,
            required=False,
            description="Username"
        ),
        ColumnSchema(
            name="balance_after",
            display_name="Saldo Setelah",
            column_type=ColumnType.CURRENCY,
            required=False,
            description="Saldo setelah transaksi"
        ),
        ColumnSchema(
            name="notes",
            display_name="Catatan",
            column_type=ColumnType.STRING,
            required=False,
            description="Catatan tambahan"
        )
    ]
)

USERS_SCHEMA = SheetSchema(
    name="USERS",
    display_name="Pengguna",
    description="Data anggota grup",
    primary_key="user_id",
    columns=[
        ColumnSchema(
            name="user_id",
            display_name="User ID",
            column_type=ColumnType.INTEGER,
            required=True,
            description="ID Telegram user"
        ),
        ColumnSchema(
            name="username",
            display_name="Username",
            column_type=ColumnType.STRING,
            required=False,
            description="Username Telegram"
        ),
        ColumnSchema(
            name="first_seen",
            display_name="Pertama Dilihat",
            column_type=ColumnType.DATETIME,
            required=True,
            description="Waktu pertama kali terlihat"
        ),
        ColumnSchema(
            name="last_active",
            display_name="Terakhir Aktif",
            column_type=ColumnType.DATETIME,
            required=False,
            description="Waktu terakhir aktif"
        ),
        ColumnSchema(
            name="message_count",
            display_name="Jumlah Pesan",
            column_type=ColumnType.INTEGER,
            required=False,
            default="0",
            description="Total pesan yang dikirim"
        ),
        ColumnSchema(
            name="transaction_count",
            display_name="Jumlah Transaksi",
            column_type=ColumnType.INTEGER,
            required=False,
            default="0",
            description="Total transaksi yang dibuat"
        ),
        ColumnSchema(
            name="role",
            display_name="Role",
            column_type=ColumnType.STRING,
            required=False,
            default="member",
            validation="admin|member",
            description="Peran dalam grup"
        )
    ]
)

CONFIG_SCHEMA = SheetSchema(
    name="CONFIG",
    display_name="Konfigurasi",
    description="Pengaturan grup",
    primary_key="key",
    columns=[
        ColumnSchema(
            name="key",
            display_name="Kunci",
            column_type=ColumnType.STRING,
            required=True,
            description="Nama pengaturan"
        ),
        ColumnSchema(
            name="value",
            display_name="Nilai",
            column_type=ColumnType.STRING,
            required=True,
            description="Nilai pengaturan"
        ),
        ColumnSchema(
            name="description",
            display_name="Deskripsi",
            column_type=ColumnType.STRING,
            required=False,
            description="Deskripsi pengaturan"
        ),
        ColumnSchema(
            name="updated_at",
            display_name="Diperbarui",
            column_type=ColumnType.DATETIME,
            required=False,
            description="Waktu terakhir diperbarui"
        )
    ]
)

AI_MEMORY_SCHEMA = SheetSchema(
    name="AI_MEMORY",
    display_name="Memori AI",
    description="Konteks percakapan untuk AI",
    primary_key="id",
    columns=[
        ColumnSchema(
            name="id",
            display_name="ID",
            column_type=ColumnType.STRING,
            required=True,
            description="ID unik memori"
        ),
        ColumnSchema(
            name="timestamp",
            display_name="Waktu",
            column_type=ColumnType.DATETIME,
            required=True,
            description="Waktu entri"
        ),
        ColumnSchema(
            name="user_id",
            display_name="User ID",
            column_type=ColumnType.INTEGER,
            required=True,
            description="ID user"
        ),
        ColumnSchema(
            name="username",
            display_name="Username",
            column_type=ColumnType.STRING,
            required=False,
            description="Username"
        ),
        ColumnSchema(
            name="message",
            display_name="Pesan",
            column_type=ColumnType.STRING,
            required=True,
            description="Pesan user"
        ),
        ColumnSchema(
            name="intent",
            display_name="Intent",
            column_type=ColumnType.STRING,
            required=False,
            description="Intent yang terdeteksi"
        ),
        ColumnSchema(
            name="response",
            display_name="Respons",
            column_type=ColumnType.STRING,
            required=False,
            description="Respons bot"
        ),
        ColumnSchema(
            name="embedding_id",
            display_name="Embedding ID",
            column_type=ColumnType.STRING,
            required=False,
            description="ID embedding untuk semantic search"
        )
    ]
)

GROUPS_SCHEMA = SheetSchema(
    name="GROUPS",
    display_name="Grup",
    description="Daftar grup yang terdaftar",
    primary_key="chat_id",
    columns=[
        ColumnSchema(
            name="chat_id",
            display_name="Chat ID",
            column_type=ColumnType.INTEGER,
            required=True,
            description="ID chat Telegram"
        ),
        ColumnSchema(
            name="chat_title",
            display_name="Nama Grup",
            column_type=ColumnType.STRING,
            required=True,
            description="Nama grup"
        ),
        ColumnSchema(
            name="spreadsheet_id",
            display_name="Spreadsheet ID",
            column_type=ColumnType.STRING,
            required=True,
            description="ID Google Spreadsheet"
        ),
        ColumnSchema(
            name="spreadsheet_url",
            display_name="URL Spreadsheet",
            column_type=ColumnType.STRING,
            required=False,
            description="URL Google Spreadsheet"
        ),
        ColumnSchema(
            name="admin_user_id",
            display_name="Admin ID",
            column_type=ColumnType.INTEGER,
            required=True,
            description="ID admin grup"
        ),
        ColumnSchema(
            name="admin_username",
            display_name="Admin Username",
            column_type=ColumnType.STRING,
            required=False,
            description="Username admin"
        ),
        ColumnSchema(
            name="status",
            display_name="Status",
            column_type=ColumnType.STRING,
            required=True,
            default="pending",
            validation="pending|active|inactive|suspended",
            description="Status grup"
        ),
        ColumnSchema(
            name="created_at",
            display_name="Dibuat",
            column_type=ColumnType.DATETIME,
            required=True,
            description="Waktu dibuat"
        ),
        ColumnSchema(
            name="last_active",
            display_name="Terakhir Aktif",
            column_type=ColumnType.DATETIME,
            required=False,
            description="Waktu terakhir aktif"
        ),
        ColumnSchema(
            name="member_count",
            display_name="Jumlah Anggota",
            column_type=ColumnType.INTEGER,
            required=False,
            default="0",
            description="Jumlah anggota"
        ),
        ColumnSchema(
            name="transaction_count",
            display_name="Jumlah Transaksi",
            column_type=ColumnType.INTEGER,
            required=False,
            default="0",
            description="Total transaksi"
        )
    ]
)

SchemaRegistry.register(TRANSACTIONS_SCHEMA)
SchemaRegistry.register(USERS_SCHEMA)
SchemaRegistry.register(CONFIG_SCHEMA)
SchemaRegistry.register(AI_MEMORY_SCHEMA)
SchemaRegistry.register(GROUPS_SCHEMA)


def get_all_headers() -> Dict[str, List[str]]:
    """Get all headers for all schemas."""
    return {
        name: schema.get_headers()
        for name, schema in SchemaRegistry.get_all().items()
    }


def validate_transaction(row: List[str]) -> Dict[str, Any]:
    """Validate a transaction row."""
    return TRANSACTIONS_SCHEMA.validate_row(row)


def validate_user(row: List[str]) -> Dict[str, Any]:
    """Validate a user row."""
    return USERS_SCHEMA.validate_row(row)
