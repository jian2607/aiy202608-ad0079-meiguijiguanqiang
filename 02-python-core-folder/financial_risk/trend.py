"""历史趋势评分，与指标公式和最终评分解耦。"""

from __future__ import annotations

from collections import defaultdict

from .curves import interpolate, tier_value
from .interfaces import Record


class TrendScorer:
    """只比较同一公司的可比报告类型；以风险区间偏离而非原始值判断恶化。"""

    def __init__(self, trend_rules: dict, metric_rules: dict):
        self.stable_score = float(trend_rules["stable_score"])
        self.magnitude_bands = trend_rules["magnitude_bands"]
        self.magnitude_top_score = float(trend_rules["magnitude_top_score"])
        self.consecutive_tiers = trend_rules["consecutive_tiers"]
        self.metric_rules = metric_rules
        self.uses_risk_distance = all(isinstance(rule, dict) and "anchors" in rule for rule in metric_rules.values())
        self.directions = metric_rules if not self.uses_risk_distance else {}

    def transform(self, records: list[Record]) -> list[Record]:
        by_series: dict[tuple[str, str], list[Record]] = defaultdict(list)
        for record in records:
            key = (str(record.get("ts_code", "")), str(record.get("statement_type", "OTHER")))
            by_series[key].append(record)
        result: list[Record] = []
        for series in by_series.values():
            series.sort(key=lambda item: str(item.get("report_period", "")))
            prior: dict[str, float | None] | None = None
            consecutive: dict[str, int] = defaultdict(int)
            for record in series:
                scores = {metric: self._score_metric(metric, value, prior, consecutive) for metric, value in record["metrics"].items()}
                result.append({**record, "trend_scores": scores, "has_prior_history": prior is not None})
                prior = record["metrics"]
        return sorted(result, key=lambda item: (str(item.get("ts_code", "")), str(item.get("report_period", ""))))

    def _score_metric(self, metric: str, value: float | None, prior: dict[str, float | None] | None, consecutive: dict[str, int]) -> float:
        if value is None or prior is None or prior.get(metric) is None:
            return self.stable_score
        change = self._risk_change(metric, value, prior[metric])
        if not self._is_worsening(metric, change):
            consecutive[metric] = 0
            return self.stable_score
        consecutive[metric] += 1
        base = self._magnitude_score(abs(change))
        tier = tier_value(self.consecutive_tiers, consecutive[metric], "minimum_periods")
        if tier is None:
            return base
        return float(tier["score"]) if tier["mode"] == "override" else max(base, float(tier["score"]))

    def _risk_change(self, metric: str, value: float, before: float) -> float:
        if self.uses_risk_distance:
            return interpolate(self.metric_rules[metric]["anchors"], value) - interpolate(self.metric_rules[metric]["anchors"], before)
        return (value - before) / max(abs(before), 1e-8)

    def _is_worsening(self, metric: str, change: float) -> bool:
        if self.uses_risk_distance:
            return change > 0
        return change > 0 if self.directions.get(metric, "high") == "high" else change < 0

    def _magnitude_score(self, magnitude: float) -> float:
        for band in self.magnitude_bands:
            if magnitude <= band["upper"]:
                return float(band["score"])
        return self.magnitude_top_score
