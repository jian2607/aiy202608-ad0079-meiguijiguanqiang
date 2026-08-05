from __future__ import annotations

from typing import Any

from ..curves import tier_value


class SynergyEvaluator:
    def __init__(self, rules: dict[str, Any], count_params: dict[str, Any]):
        self.rules, self.max_addition = rules["rules"], float(rules["max_addition"])
        self.severe_score, self.tiers = float(count_params["severe_metric_score"]), count_params["tiers"]

    def evaluate(self, details: dict[str, Any]) -> dict[str, Any]:
        triggered = []
        for rule in self.rules:
            if all(details[item["metric"]]["score"] is not None and details[item["metric"]]["score"] >= item["min"] for item in rule["conditions"]):
                triggered.append({"id": rule["id"], "label": rule["label"], "addition": rule["addition"]})
        addition = min(sum(item["addition"] for item in triggered), self.max_addition)
        severe = sum(1 for item in details.values() if item["score"] is not None and item["score"] >= self.severe_score)
        tier = tier_value(self.tiers, severe, "minimum_count")
        if tier:
            triggered.append({"id": tier["id"], "label": tier["label"], "addition": tier["addition"]})
            addition = min(addition + tier["addition"], self.max_addition)
        return {"addition": addition, "triggered": triggered}
