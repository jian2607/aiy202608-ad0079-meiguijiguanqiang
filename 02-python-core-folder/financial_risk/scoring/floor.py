from __future__ import annotations

from ..interfaces import Record


class RiskFloorEvaluator:
    def __init__(self, params: dict):
        self.params = params

    def evaluate(self, record: Record) -> tuple[float, list[str]]:
        floor, reasons = 0.0, []
        checks = [
            (record.get("equity") is not None and record["equity"] < 0, self.params["negative_equity"]),
            (any(keyword in str(record.get("audit_opinion") or "") for keyword in self.params["adverse_audit_opinion"]["keywords"]), self.params["adverse_audit_opinion"]),
            (str(record.get("regulatory_rule_triggered", "")).lower() in {str(x).lower() for x in self.params["regulatory_flag"]["truthy_values"]}, self.params["regulatory_flag"]),
        ]
        for triggered, rule in checks:
            if triggered:
                floor = max(floor, float(rule["score"]))
                reasons.append(rule["reason"])
        for trigger in record.get("rule_triggers", []):
            floor = max(floor, float(trigger["score"]))
            suffix = "（需人工复核）" if trigger.get("review_required") else ""
            reasons.append(f"{trigger['id']}：{trigger['label']}，风险下限{trigger['score']:.0f}{suffix}")
        audit_score, audit_reason = self._audit_score(record.get("audit_opinion"))
        if audit_score > 0:
            floor = max(floor, audit_score)
            reasons.append(audit_reason)
        return floor, reasons

    def _audit_score(self, opinion: object) -> tuple[float, str]:
        text = str(opinion or "")
        for item in self.params.get("audit_opinion_grades", []):
            if any(keyword in text for keyword in item["keywords"]):
                return float(item["score"]), item["reason"]
        return 0.0, ""
