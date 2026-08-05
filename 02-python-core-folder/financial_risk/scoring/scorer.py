from __future__ import annotations

from ..config import AppConfig
from ..interfaces import Assessment, Record, ReferenceModel
from .aggregation import DimensionAggregator
from .confidence import ConfidenceEvaluator
from .floor import RiskFloorEvaluator
from .metric_scorer import MetricScorer
from .scales import PeerScale
from .synergy import SynergyEvaluator


class RiskScorer:
    def __init__(self, config: AppConfig):
        params = config.scoring_params
        self.metrics = config.metrics
        self.maximum_score = float(params["aggregation"]["maximum_score"])
        self.metric_scorer = MetricScorer(config.metrics, params, PeerScale(params["peer"]))
        self.aggregator = DimensionAggregator(config.weights["groups"], params["aggregation"])
        self.synergy = SynergyEvaluator(config.synergy_rules, params["count_synergy"])
        self.floor = RiskFloorEvaluator(params["risk_floor"])
        self.confidence = ConfidenceEvaluator(params["confidence"], params["risk_levels"])

    def assess(self, record: Record, reference: ReferenceModel) -> Assessment:
        details = {metric: self.metric_scorer.score(record, metric, reference) for metric in self.metrics}
        dimensions = self.aggregator.by_dimension(details)
        base_score, coverage = self.aggregator.total(dimensions)
        synergy = self.synergy.evaluate(details)
        floor, reasons = self.floor.evaluate(record)
        computed_score = None if base_score is None else min(self.maximum_score, base_score + synergy["addition"])
        if base_score is None:
            # No usable metric scores: report only an explicit hard-rule floor.
            final_score = floor if floor > 0 else None
        else:
            final_score = max(computed_score, floor)
        confidence = self.confidence.evaluate(record, details, dimensions)
        return {"ts_code": record.get("ts_code"), "company_name": record.get("company_name"), "report_period": record.get("report_period"), "ann_date": record.get("ann_date"), "risk_score": round(final_score, 2) if final_score is not None else None, "base_score": round(base_score, 2) if base_score is not None else None, "computed_score": round(computed_score, 2) if computed_score is not None else None, "risk_level": self.confidence.risk_level(final_score, confidence), "data_confidence": confidence, "dimensions": dimensions, "metrics": details, "synergy": synergy, "risk_floor": {"score": floor, "reasons": reasons}, "rule_triggers": record.get("rule_triggers", []), "calculation_notes": record.get("calculation_notes", {}), "versions": {}, "base_coverage": round(coverage, 4)}
