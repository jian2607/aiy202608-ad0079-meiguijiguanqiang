"""数据质量校验，不静默删除输入记录。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .utils import safe_div


class DataQualityError(ValueError):
    """输入未达到正式训练或评估的最低质量门槛。"""


class DataQualityValidator:
    def __init__(self, rules: dict[str, Any]):
        self.rules = rules

    def validate(self, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        issues: list[dict[str, Any]] = []
        seen: dict[tuple[str, str], list[int]] = defaultdict(list)
        warning_difference = float(self.rules["warning_balance_sheet_difference"])
        maximum_difference = float(self.rules["maximum_balance_sheet_difference"])
        for index, record in enumerate(records):
            profile = self._profile(record)
            required = tuple(profile["required_fields"])
            identifiers = set(profile["identifier_fields"])
            code = record.get("ts_code", "")
            period = record.get("report_period", "")
            seen[(code, period)].append(index)
            for field in required:
                if record.get(field) in (None, ""):
                    severity = "error" if field in identifiers else "warning"
                    issues.append(self._issue(index, record, "missing_core_field", f"缺少核心字段: {field}", severity))
            balance_ratio = safe_div(
                abs((record.get("total_assets") or 0) - (record.get("total_liabilities") or 0) - (record.get("equity") or 0)),
                abs(record.get("total_assets") or 0),
            )
            if balance_ratio is not None and balance_ratio > maximum_difference:
                issues.append(self._issue(index, record, "balance_sheet_unbalanced", f"资产负债表不平衡，差异率={balance_ratio:.2%}", "error"))
            elif balance_ratio is not None and balance_ratio > warning_difference:
                issues.append(self._issue(index, record, "balance_sheet_tolerance", f"资产负债表差异率={balance_ratio:.2%}", "warning"))
            if (record.get("total_assets") is not None) and record["total_assets"] < 0:
                issues.append(self._issue(index, record, "negative_total_assets", "总资产为负", "error"))

        for (code, period), indices in seen.items():
            if len(indices) > 1:
                for index in indices:
                    issues.append(self._issue(index, records[index], "duplicate_company_period", f"公司-报告期重复: {code}-{period}", "warning"))
        return records, issues

    def summary(self, records: list[dict[str, Any]], issues: list[dict[str, Any]]) -> dict[str, Any]:
        total_values = max(1, sum(len(self._profile(record)["required_fields"]) for record in records))
        present = sum(record.get(field) not in (None, "") for record in records for field in self._profile(record)["required_fields"])
        return {
            "record_count": len(records),
            "core_completeness": round(present / total_values, 4),
            "minimum_core_completeness": float(self.rules["minimum_core_completeness"]),
            "errors": sum(issue["severity"] == "error" for issue in issues),
            "warnings": sum(issue["severity"] == "warning" for issue in issues),
            "ready": not any(issue["severity"] == "error" for issue in issues) and present / total_values >= float(self.rules["minimum_core_completeness"]),
        }

    def _profile(self, record: dict[str, Any]) -> dict[str, Any]:
        source = str(record.get("data_source") or "")
        override = self.rules.get("source_profiles", {}).get(source, {})
        return {**self.rules, **override}

    def assert_ready(self, summary: dict[str, Any], allow_errors: bool = False) -> None:
        if self.rules.get("block_on_error", True) and not summary["ready"] and not allow_errors:
            raise DataQualityError(
                f"数据质量未达到正式运行门槛：errors={summary['errors']}，"
                f"core_completeness={summary['core_completeness']:.2%}。"
                "请先执行 prepare 检查，或仅在实验场景使用 --allow-errors。"
            )

    @staticmethod
    def _issue(index: int, record: dict[str, Any], code: str, message: str, severity: str) -> dict[str, Any]:
        return {"row_index": index, "ts_code": record.get("ts_code"), "report_period": record.get("report_period"), "code": code, "message": message, "severity": severity}
