"""将原始导入记录转换为可重复使用的标准财务记录。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..interfaces import Record


MONETARY_FIELDS = {
    "total_assets", "total_liabilities", "equity", "current_assets", "current_liabilities",
    "inventory", "accounts_receivable", "cash", "short_term_debt",
    "current_portion_long_term_debt", "revenue", "operating_cost", "net_profit",
    "deducted_net_profit", "operating_cashflow", "goodwill", "ebit", "interest_expense",
}
UNIT_MULTIPLIERS = {
    "元": 1.0, "人民币元": 1.0, "cny": 1.0,
    "千元": 1_000.0, "万元": 10_000.0, "百万元": 1_000_000.0,
    "亿元": 100_000_000.0,
}


class DataPreprocessor:
    """日期、报表类型、金额单位与更正版本的确定性处理。"""

    def __init__(self, options: dict[str, Any] | None = None):
        options = options or {}
        self.options = options
        self.default_unit = str(options.get("default_amount_unit", "元"))

    def normalize(self, records: list[Record]) -> tuple[list[Record], list[dict[str, Any]]]:
        issues: list[dict[str, Any]] = []
        normalized: list[Record] = []
        for index, record in enumerate(records):
            row = dict(record)
            report_period = self._date(row.get("report_period"))
            ann_date = self._date(row.get("ann_date"))
            if report_period is None:
                issues.append(self._issue(index, row, "invalid_report_period", "报告期必须为有效日期", "error"))
            else:
                row["report_period"] = report_period.isoformat()
                row["fiscal_year"] = report_period.year
                row["statement_type"] = self._statement_type(report_period)
                if row["statement_type"] == "OTHER":
                    issues.append(self._issue(index, row, "unsupported_statement_type", "仅支持季度末报告期（3月、6月、9月、12月）", "error"))
                allowed = self._source_profile(row).get("allowed_statement_types")
                if allowed and row["statement_type"] not in allowed:
                    issues.append(self._issue(index, row, "unsupported_source_period", f"数据源 {row.get('data_source')} 仅处理报告类型: {','.join(allowed)}", "error"))
            if ann_date is None:
                issues.append(self._issue(index, row, "invalid_ann_date", "公告日期必须为有效日期", "warning"))
            else:
                row["ann_date"] = ann_date.isoformat()
            self._normalize_unit(row, index, issues)
            row["source_row_index"] = index
            normalized.append(row)
        return normalized, issues

    def canonicalize_revisions(self, records: list[Record]) -> tuple[list[Record], list[dict[str, Any]], list[dict[str, Any]]]:
        """同一公司同一报告期只保留最后公告版本，并保留全部处理血缘。"""
        groups: dict[tuple[str, str], list[Record]] = {}
        for row in records:
            key = (str(row.get("ts_code") or ""), str(row.get("report_period") or ""))
            groups.setdefault(key, []).append(row)
        canonical, issues, lineage = [], [], []
        for key, rows in groups.items():
            ordered = sorted(rows, key=lambda row: (str(row.get("ann_date") or ""), int(row.get("source_row_index", -1))))
            chosen = ordered[-1]
            canonical.append(chosen)
            if len(ordered) > 1:
                chosen_date = chosen.get("ann_date") or "缺失"
                same_date = [row for row in ordered if row.get("ann_date") == chosen.get("ann_date")]
                if len(same_date) > 1:
                    issues.append(self._issue(int(chosen.get("source_row_index", -1)), chosen, "ambiguous_revision", "同公司同报告期存在相同公告日期的多个版本，按最后出现记录保留", "warning"))
                for row in ordered[:-1]:
                    lineage.append({"ts_code": key[0], "report_period": key[1], "source_row_index": row.get("source_row_index"), "action": "superseded", "selected_source_row_index": chosen.get("source_row_index"), "selected_ann_date": chosen_date})
                lineage.append({"ts_code": key[0], "report_period": key[1], "source_row_index": chosen.get("source_row_index"), "action": "selected", "selected_source_row_index": chosen.get("source_row_index"), "selected_ann_date": chosen_date})
            else:
                lineage.append({"ts_code": key[0], "report_period": key[1], "source_row_index": chosen.get("source_row_index"), "action": "selected", "selected_source_row_index": chosen.get("source_row_index"), "selected_ann_date": chosen.get("ann_date")})
        return sorted(canonical, key=lambda row: (str(row.get("ts_code") or ""), str(row.get("report_period") or ""))), issues, lineage

    @staticmethod
    def _date(value: Any) -> date | None:
        if value is None or str(value).strip() == "":
            return None
        text = str(value).strip().replace("/", "-")
        if len(text) == 8 and text.isdigit():
            text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _statement_type(report_period: date) -> str:
        return {3: "Q1", 6: "H1", 9: "Q3", 12: "FY"}.get(report_period.month, "OTHER")

    def _normalize_unit(self, row: Record, index: int, issues: list[dict[str, Any]]) -> None:
        supplied = str(row.get("amount_unit") or self.default_unit).strip().lower()
        multiplier = UNIT_MULTIPLIERS.get(supplied)
        if multiplier is None:
            issues.append(self._issue(index, row, "unknown_amount_unit", f"无法识别金额单位: {supplied}", "warning"))
            row["amount_unit"] = supplied
            return
        for field in MONETARY_FIELDS:
            value = row.get(field)
            if value is not None:
                row[field] = value * multiplier
        row["amount_unit"] = "元"

    def _source_profile(self, row: Record) -> dict[str, Any]:
        return self.options.get("source_profiles", {}).get(str(row.get("data_source") or ""), {})

    @staticmethod
    def _issue(index: int, row: Record, code: str, message: str, severity: str) -> dict[str, Any]:
        return {"row_index": index, "ts_code": row.get("ts_code"), "report_period": row.get("report_period"), "code": code, "message": message, "severity": severity}
