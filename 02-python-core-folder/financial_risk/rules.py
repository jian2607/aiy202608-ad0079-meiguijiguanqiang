"""配置驱动的硬性风险规则；规则结论需保留人工复核状态。"""

from __future__ import annotations

from typing import Any

from .interfaces import Record


class HardRuleEngine:
    def __init__(self, config: dict[str, Any]):
        self.rules = config.get("rules", [])

    def evaluate(self, record: Record) -> list[dict[str, Any]]:
        triggered = []
        for rule in self.rules:
            if all(self._matches(record.get(item["field"]), item) for item in rule.get("conditions", [])):
                triggered.append({"id": rule["id"], "label": rule["label"], "score": float(rule["score"]), "review_required": bool(rule.get("review_required", True))})
        return triggered

    @staticmethod
    def _matches(actual: Any, condition: dict[str, Any]) -> bool:
        if actual is None or actual == "":
            return False
        expected, operator = condition.get("value"), condition.get("operator")
        try:
            if operator == "lt": return float(actual) < float(expected)
            if operator == "lte": return float(actual) <= float(expected)
            if operator == "gt": return float(actual) > float(expected)
            if operator == "gte": return float(actual) >= float(expected)
        except (TypeError, ValueError):
            return False
        if operator == "eq": return str(actual) == str(expected)
        if operator == "contains": return str(expected) in str(actual)
        if operator == "in": return str(actual) in {str(value) for value in expected}
        return False
