# path: app/admin/reports.py
"""
Report Generator - Generates various reports for admin.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.sheets.client import SheetsClient
from app.sheets.master import MasterSheet
from app.sheets.group import GroupSheet
from app.infra.logger import get_logger
from app.infra.utils import format_currency


logger = get_logger(__name__)


@dataclass
class ReportData:
    """Container for report data."""
    title: str
    generated_at: str
    period_start: str
    period_end: str
    data: Dict[str, Any]
    summary: str


class ReportGenerator:
    """
    Generates various reports for admin and groups.
    """

    def __init__(
        self,
        sheets_client: SheetsClient,
        master_sheet: MasterSheet
    ):
        self.sheets_client = sheets_client
        self.master_sheet = master_sheet

    async def generate_system_report(
        self,
        period_days: int = 30
    ) -> ReportData:
        """
        Generate system-wide report.

        Args:
            period_days: Report period in days

        Returns:
            System report data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        stats = await self.master_sheet.get_stats()
        groups = await self.master_sheet.get_all_groups()

        active_count = len([g for g in groups if g.get("status") == "active"])
        total_transactions = sum(g.get("transaction_count", 0) for g in groups)

        new_groups = []
        for group in groups:
            created_at = group.get("created_at")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at)
                    if created_dt >= start_date:
                        new_groups.append(group)
                except ValueError:
                    pass

        data = {
            "total_groups": len(groups),
            "active_groups": active_count,
            "new_groups": len(new_groups),
            "total_transactions": total_transactions,
            "super_admins": stats.get("super_admins", 0),
            "groups_by_status": {
                "active": active_count,
                "suspended": len([g for g in groups if g.get("status") == "suspended"]),
                "inactive": len([g for g in groups if g.get("status") == "inactive"])
            },
            "top_groups": sorted(
                groups,
                key=lambda x: x.get("transaction_count", 0),
                reverse=True
            )[:5]
        }

        summary = (
            f"Dalam {period_days} hari terakhir:\n"
            f"- {len(new_groups)} grup baru terdaftar\n"
            f"- {active_count} grup aktif\n"
            f"- {total_transactions} total transaksi"
        )

        return ReportData(
            title="Laporan Sistem",
            generated_at=datetime.now().isoformat(),
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            data=data,
            summary=summary
        )

    async def generate_group_report(
        self,
        chat_id: int,
        period_days: int = 30
    ) -> Optional[ReportData]:
        """
        Generate report for a specific group.

        Args:
            chat_id: The chat ID
            period_days: Report period in days

        Returns:
            Group report data or None
        """
        group_data = await self.master_sheet.get_group(chat_id)
        if not group_data:
            return None

        spreadsheet_id = group_data.get("spreadsheet_id")
        if not spreadsheet_id:
            return None

        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        try:
            group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)

            report = await group_sheet.get_report(start_date, end_date)
            balance_data = await group_sheet.get_balance()

            data = {
                "group_name": group_data.get("chat_title"),
                "period": f"{period_days} hari",
                "total_income": report.get("total_income", 0),
                "total_expense": report.get("total_expense", 0),
                "balance": balance_data.get("balance", 0),
                "income_count": report.get("income_count", 0),
                "expense_count": report.get("expense_count", 0),
                "transaction_count": report.get("transaction_count", 0),
                "top_expenses": report.get("top_expenses", []),
                "category_breakdown": report.get("category_breakdown", {})
            }

            net = data["total_income"] - data["total_expense"]
            net_label = "surplus" if net >= 0 else "defisit"

            summary = (
                f"Periode: {period_days} hari terakhir\n"
                f"Total Pemasukan: {format_currency(data['total_income'])}\n"
                f"Total Pengeluaran: {format_currency(data['total_expense'])}\n"
                f"Net: {format_currency(abs(net))} ({net_label})\n"
                f"Saldo Akhir: {format_currency(data['balance'])}"
            )

            return ReportData(
                title=f"Laporan {group_data.get('chat_title')}",
                generated_at=datetime.now().isoformat(),
                period_start=start_date.isoformat(),
                period_end=end_date.isoformat(),
                data=data,
                summary=summary
            )

        except Exception as e:
            logger.error(f"Error generating group report: {e}")
            return None

    async def generate_activity_report(
        self,
        period_days: int = 7
    ) -> ReportData:
        """
        Generate activity report showing group activities.

        Args:
            period_days: Report period in days

        Returns:
            Activity report data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        groups = await self.master_sheet.get_all_groups(status="active")

        active_groups = []
        inactive_groups = []

        for group in groups:
            last_active = group.get("last_active")
            if last_active:
                try:
                    last_active_dt = datetime.fromisoformat(last_active)
                    if last_active_dt >= start_date:
                        active_groups.append(group)
                    else:
                        group["days_inactive"] = (end_date - last_active_dt).days
                        inactive_groups.append(group)
                except ValueError:
                    inactive_groups.append(group)

        data = {
            "period_days": period_days,
            "active_in_period": len(active_groups),
            "inactive_in_period": len(inactive_groups),
            "active_groups": active_groups,
            "inactive_groups": sorted(
                inactive_groups,
                key=lambda x: x.get("days_inactive", 0),
                reverse=True
            )
        }

        summary = (
            f"Dalam {period_days} hari terakhir:\n"
            f"- {len(active_groups)} grup aktif\n"
            f"- {len(inactive_groups)} grup tidak aktif"
        )

        return ReportData(
            title="Laporan Aktivitas",
            generated_at=datetime.now().isoformat(),
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            data=data,
            summary=summary
        )

    async def generate_financial_summary(
        self,
        period_days: int = 30
    ) -> ReportData:
        """
        Generate financial summary across all groups.

        Args:
            period_days: Report period in days

        Returns:
            Financial summary data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        groups = await self.master_sheet.get_all_groups(status="active")

        total_income = 0
        total_expense = 0
        total_balance = 0
        group_summaries = []

        for group in groups:
            spreadsheet_id = group.get("spreadsheet_id")
            if not spreadsheet_id:
                continue

            try:
                group_sheet = GroupSheet(self.sheets_client, spreadsheet_id)
                report = await group_sheet.get_report(start_date, end_date)
                balance = await group_sheet.get_balance()

                income = report.get("total_income", 0)
                expense = report.get("total_expense", 0)
                bal = balance.get("balance", 0)

                total_income += income
                total_expense += expense
                total_balance += bal

                group_summaries.append({
                    "name": group.get("chat_title"),
                    "income": income,
                    "expense": expense,
                    "balance": bal
                })

            except Exception as e:
                logger.error(f"Error getting data for group: {e}")

        group_summaries.sort(key=lambda x: x["balance"], reverse=True)

        data = {
            "total_groups_analyzed": len(group_summaries),
            "total_income": total_income,
            "total_expense": total_expense,
            "total_balance": total_balance,
            "top_by_balance": group_summaries[:5],
            "top_by_income": sorted(
                group_summaries,
                key=lambda x: x["income"],
                reverse=True
            )[:5],
            "top_by_expense": sorted(
                group_summaries,
                key=lambda x: x["expense"],
                reverse=True
            )[:5]
        }

        summary = (
            f"Total {len(group_summaries)} grup dianalisis:\n"
            f"Total Pemasukan: {format_currency(total_income)}\n"
            f"Total Pengeluaran: {format_currency(total_expense)}\n"
            f"Total Saldo: {format_currency(total_balance)}"
        )

        return ReportData(
            title="Ringkasan Keuangan",
            generated_at=datetime.now().isoformat(),
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
            data=data,
            summary=summary
        )

    def format_report_text(self, report: ReportData) -> str:
        """
        Format a report as text for display.

        Args:
            report: The report data

        Returns:
            Formatted text
        """
        lines = [
            f"<b>📊 {report.title}</b>",
            f"<i>Generated: {report.generated_at[:10]}</i>",
            "",
            report.summary,
            "",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        if "total_income" in report.data:
            lines.append(f"💰 Pemasukan: {format_currency(report.data['total_income'])}")

        if "total_expense" in report.data:
            lines.append(f"💸 Pengeluaran: {format_currency(report.data['total_expense'])}")

        if "balance" in report.data:
            lines.append(f"🏦 Saldo: {format_currency(report.data['balance'])}")

        if "top_groups" in report.data and report.data["top_groups"]:
            lines.append("")
            lines.append("<b>Top Grup:</b>")
            for i, group in enumerate(report.data["top_groups"][:5], 1):
                lines.append(f"{i}. {group.get('chat_title', 'Unknown')}")

        return "\n".join(lines)
