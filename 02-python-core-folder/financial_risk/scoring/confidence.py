from __future__ import annotations

from typing import Any

from ..interfaces import Record


class ConfidenceEvaluator:
    def __init__(self, params: dict[str, Any], level_params: dict[str, Any]):
        self.params, self.level_params = params, level_params

    def evaluate(self, record: Record, details: dict[str, Any], dimensions: dict[str, Any]) -> dict[str, Any]:
        completeness = sum(item["score"] is not None for item in details.values()) / len(details)
        group_coverage = sum(item["score"] is not None for item in dimensions.values()) / len(dimensions)
        weights = self.params["weights"]
        present, absent = self.params["presence_scores"]["present"], self.params["presence_scores"]["absent"]
        score = 100 * (weights["metric_completeness"] * completeness + weights["audit_opinion"] * (present if record.get("audit_opinion") else absent) + weights["prior_history"] * (present if record.get("has_prior_history") else absent) + weights["group_coverage"] * group_coverage)
        level = next((item["label"] for item in self.params["levels"] if score >= item["minimum"]), self.params["fallback_level"])
        return {"score": round(score, 2), "level": level, "metric_completeness": round(completeness, 4)}

    def risk_level(self, score: float | None, confidence: dict[str, Any]) -> str:
        if score is None or confidence["score"] < self.level_params["minimum_confidence"]:
            return self.level_params["unverified_label"]
        for band in self.level_params["bands"]:
            if score <= band["upper"]:
                return band["label"]
        return self.level_params["top_label"]
