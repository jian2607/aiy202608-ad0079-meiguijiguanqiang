from __future__ import annotations

from pathlib import Path
from typing import Any

from financial_risk.pipeline import FinancialRiskPipeline
from financial_risk.reference import IndustryReferenceModel


class FinancialRiskEngineAdapter:
    """Adapts the standalone deterministic model to application use cases."""

    def __init__(self, model_dir: str | Path):
        self.pipeline = FinancialRiskPipeline()
        reference_path = Path(model_dir) / "industry_reference.json"
        if not reference_path.exists():
            raise FileNotFoundError(f"缺少行业参考模型: {reference_path}")
        self.reference = IndustryReferenceModel.load(reference_path)

    def prepare_csv(self, file_path: str) -> dict[str, Any]:
        prepared = self.pipeline._prepare(file_path)
        return {"records": prepared["records"], "issues": prepared["issues"], "quality_summary": prepared["quality_summary"]}

    def assess(self, report_history: list[dict[str, Any]]) -> dict[str, Any]:
        enriched = self.pipeline.trend.transform(self.pipeline.calculator.transform(report_history))
        enriched = [{**record, "rule_triggers": self.pipeline.rules.evaluate(record)} for record in enriched]
        assessment = self.pipeline.scorer.assess(enriched[-1], self.reference)
        assessment["versions"] = {**self.pipeline.configs.versions(), "reference": self.reference.version}
        assessment["statement_type"] = report_history[-1].get("statement_type")
        return assessment
