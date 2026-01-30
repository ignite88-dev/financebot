# path: app/sheets/templates.py
"""
Spreadsheet templates for group initialization.
"""

from typing import Dict, Any, List
from datetime import datetime

from app.infra.logger import get_logger


logger = get_logger(__name__)


class SpreadsheetTemplates:
    """
    Templates for creating and initializing spreadsheets.
    """

    @staticmethod
    def get_group_template() -> Dict[str, Any]:
        """
        Get the template for a new group spreadsheet.

        Returns:
            Dict containing sheet definitions and initial data
        """
        return {
            "sheets": [
                {
                    "name": "CONFIG",
                    "headers": ["key", "value", "description", "updated_at"],
                    "initial_data": [
                        ["group_name", "", "Nama grup", ""],
                        ["admin_user_id", "", "ID admin utama", ""],
                        ["language", "id", "Bahasa (id/en)", ""],
                        ["currency", "IDR", "Mata uang", ""],
                        ["persona", "professional", "Persona bot", ""],
                        ["timezone", "Asia/Jakarta", "Zona waktu", ""],
                        ["notifications", "true", "Notifikasi aktif", ""],
                        ["auto_report", "weekly", "Laporan otomatis", ""],
                        ["created_at", "", "Waktu dibuat", ""],
                        ["status", "active", "Status grup", ""]
                    ],
                    "column_widths": [150, 200, 250, 150]
                },
                {
                    "name": "USERS",
                    "headers": [
                        "user_id", "username", "first_seen", "last_active",
                        "message_count", "transaction_count", "role"
                    ],
                    "initial_data": [],
                    "column_widths": [120, 150, 180, 180, 100, 120, 100]
                },
                {
                    "name": "TRANSACTIONS",
                    "headers": [
                        "id", "timestamp", "type", "amount", "description",
                        "category", "user_id", "username", "balance_after", "notes"
                    ],
                    "initial_data": [],
                    "column_widths": [150, 180, 80, 120, 250, 120, 100, 120, 120, 200]
                },
                {
                    "name": "JOURNAL",
                    "headers": ["id", "timestamp", "type", "content", "user_id", "username"],
                    "initial_data": [],
                    "column_widths": [150, 180, 100, 400, 100, 120]
                },
                {
                    "name": "AI_MEMORY",
                    "headers": [
                        "id", "timestamp", "user_id", "username",
                        "message", "intent", "response", "embedding_id"
                    ],
                    "initial_data": [],
                    "column_widths": [150, 180, 100, 120, 300, 150, 300, 150]
                },
                {
                    "name": "AUDIT_LOG",
                    "headers": [
                        "timestamp", "action", "user_id", "username",
                        "details", "ip_address"
                    ],
                    "initial_data": [],
                    "column_widths": [180, 150, 100, 120, 350, 120]
                },
                {
                    "name": "CATEGORIES",
                    "headers": ["name", "type", "description", "budget_limit"],
                    "initial_data": [
                        ["Iuran", "income", "Iuran anggota", "0"],
                        ["Donasi", "income", "Donasi/sumbangan", "0"],
                        ["Lainnya", "income", "Pemasukan lainnya", "0"],
                        ["Operasional", "expense", "Biaya operasional", "0"],
                        ["Peralatan", "expense", "Pembelian peralatan", "0"],
                        ["Konsumsi", "expense", "Makanan dan minuman", "0"],
                        ["Transport", "expense", "Biaya transportasi", "0"],
                        ["Acara", "expense", "Biaya acara/kegiatan", "0"],
                        ["Lainnya", "expense", "Pengeluaran lainnya", "0"]
                    ],
                    "column_widths": [150, 100, 250, 120]
                },
                {
                    "name": "BUDGETS",
                    "headers": [
                        "period", "category", "budget_amount",
                        "spent_amount", "remaining", "status"
                    ],
                    "initial_data": [],
                    "column_widths": [120, 150, 120, 120, 120, 100]
                }
            ],
            "formatting": {
                "header_color": {"red": 0.2, "green": 0.4, "blue": 0.8},
                "header_text_color": {"red": 1, "green": 1, "blue": 1},
                "freeze_rows": 1
            }
        }

    @staticmethod
    def get_master_template() -> Dict[str, Any]:
        """
        Get the template for the master admin spreadsheet.

        Returns:
            Dict containing sheet definitions
        """
        return {
            "sheets": [
                {
                    "name": "GROUPS",
                    "headers": [
                        "chat_id", "chat_title", "spreadsheet_id", "spreadsheet_url",
                        "admin_user_id", "admin_username", "status", "created_at",
                        "last_active", "member_count", "transaction_count"
                    ],
                    "initial_data": [],
                    "column_widths": [120, 200, 300, 400, 120, 150, 100, 180, 180, 100, 120]
                },
                {
                    "name": "SUPER_ADMINS",
                    "headers": ["user_id", "username", "added_at", "added_by", "permissions"],
                    "initial_data": [],
                    "column_widths": [120, 150, 180, 150, 250]
                },
                {
                    "name": "GLOBAL_SETTINGS",
                    "headers": ["key", "value", "description", "updated_at"],
                    "initial_data": [
                        ["max_groups", "100", "Maksimum grup yang bisa terdaftar", ""],
                        ["default_language", "id", "Bahasa default", ""],
                        ["default_persona", "professional", "Persona default", ""],
                        ["ai_model", "gpt-4o-mini", "Model AI yang digunakan", ""],
                        ["maintenance_mode", "false", "Mode maintenance", ""],
                        ["version", "1.0.0", "Versi sistem", ""]
                    ],
                    "column_widths": [200, 200, 300, 180]
                },
                {
                    "name": "PERSONAS",
                    "headers": [
                        "name", "display_name", "system_prompt",
                        "greeting", "style", "is_default"
                    ],
                    "initial_data": [
                        [
                            "professional",
                            "Profesional",
                            "Kamu adalah asisten keuangan profesional. Gunakan bahasa formal dan sopan. Berikan informasi yang akurat dan terstruktur.",
                            "Selamat datang. Saya siap membantu mengelola keuangan grup Anda.",
                            "formal",
                            "true"
                        ],
                        [
                            "friendly",
                            "Ramah",
                            "Kamu adalah asisten keuangan yang ramah dan santai. Gunakan bahasa casual tapi tetap informatif. Boleh pakai emoji.",
                            "Hai! 👋 Aku siap bantu urusan keuangan grup nih!",
                            "casual",
                            "false"
                        ],
                        [
                            "efficient",
                            "Efisien",
                            "Kamu adalah asisten keuangan yang efisien. Berikan jawaban singkat, padat, dan langsung ke inti. Hindari basa-basi.",
                            "Siap membantu. Ketik perintah atau pertanyaan.",
                            "minimal",
                            "false"
                        ]
                    ],
                    "column_widths": [120, 150, 500, 300, 100, 80]
                },
                {
                    "name": "SYSTEM_LOG",
                    "headers": [
                        "timestamp", "level", "source", "message",
                        "chat_id", "user_id", "details"
                    ],
                    "initial_data": [],
                    "column_widths": [180, 80, 150, 400, 120, 120, 300]
                }
            ]
        }

    @staticmethod
    def get_default_config(
        group_name: str,
        admin_user_id: int,
        admin_username: str
    ) -> List[List[str]]:
        """
        Get default config values for a new group.

        Args:
            group_name: Name of the group
            admin_user_id: ID of the admin user
            admin_username: Username of the admin

        Returns:
            List of config rows
        """
        now = datetime.now().isoformat()

        return [
            ["group_name", group_name, "Nama grup", now],
            ["admin_user_id", str(admin_user_id), "ID admin utama", now],
            ["admin_username", admin_username, "Username admin", now],
            ["language", "id", "Bahasa (id/en)", now],
            ["currency", "IDR", "Mata uang", now],
            ["persona", "professional", "Persona bot", now],
            ["timezone", "Asia/Jakarta", "Zona waktu", now],
            ["notifications", "true", "Notifikasi aktif", now],
            ["auto_report", "weekly", "Laporan otomatis (daily/weekly/monthly/off)", now],
            ["created_at", now, "Waktu dibuat", now],
            ["status", "active", "Status grup", now]
        ]

    @staticmethod
    def get_sample_transactions() -> List[List[str]]:
        """
        Get sample transactions for demonstration.

        Returns:
            List of sample transaction rows
        """
        now = datetime.now()

        return [
            [
                "TX_SAMPLE_001",
                now.isoformat(),
                "income",
                "1000000",
                "Contoh: Iuran bulanan",
                "Iuran",
                "0",
                "system",
                "1000000",
                "Transaksi contoh - bisa dihapus"
            ]
        ]

    @staticmethod
    def format_currency_cells() -> Dict[str, Any]:
        """
        Get currency formatting for amount cells.
        """
        return {
            "numberFormat": {
                "type": "CURRENCY",
                "pattern": "Rp#,##0"
            }
        }

    @staticmethod
    def format_date_cells() -> Dict[str, Any]:
        """
        Get date formatting for timestamp cells.
        """
        return {
            "numberFormat": {
                "type": "DATE_TIME",
                "pattern": "yyyy-mm-dd hh:mm:ss"
            }
        }


class TemplateValidator:
    """
    Validates spreadsheet structure against templates.
    """

    def __init__(self, template: Dict[str, Any]):
        self.template = template

    def validate_spreadsheet(
        self,
        spreadsheet_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a spreadsheet against the template.

        Args:
            spreadsheet_info: Info about the spreadsheet to validate

        Returns:
            Validation result with missing/extra sheets and columns
        """
        result = {
            "valid": True,
            "missing_sheets": [],
            "extra_sheets": [],
            "missing_columns": {},
            "errors": []
        }

        existing_sheets = set(spreadsheet_info.get("sheets", []))
        template_sheets = {s["name"] for s in self.template["sheets"]}

        result["missing_sheets"] = list(template_sheets - existing_sheets)
        result["extra_sheets"] = list(existing_sheets - template_sheets)

        if result["missing_sheets"]:
            result["valid"] = False
            result["errors"].append(
                f"Missing sheets: {', '.join(result['missing_sheets'])}"
            )

        return result

    def get_repair_actions(
        self,
        validation_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get actions needed to repair a spreadsheet.

        Args:
            validation_result: Result from validate_spreadsheet

        Returns:
            List of repair actions
        """
        actions = []

        for sheet_name in validation_result["missing_sheets"]:
            sheet_def = next(
                (s for s in self.template["sheets"] if s["name"] == sheet_name),
                None
            )

            if sheet_def:
                actions.append({
                    "action": "create_sheet",
                    "sheet_name": sheet_name,
                    "headers": sheet_def["headers"],
                    "initial_data": sheet_def.get("initial_data", [])
                })

        return actions
