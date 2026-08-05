"""模型编排层：只组装模块，不承载评分、AI或文件格式规则。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ai import build_provider
from .config import AppConfig, DEFAULT_CONFIG_DIR, load_configs
from .environment import load_project_env
from .ingestion import CSVIngestor
from .interfaces import Assessment, Record
from .metrics import MetricCalculator
from .preprocessing import DataPreprocessor
from .quality import DataQualityValidator
from .reference import IndustryReferenceModel
from .registry import ModelRegistry
from .reporting import ResultWriter, build_manifest
from .rules import HardRuleEngine
from .scoring import RiskScorer
from .sources import BaoStockCollector
from .storage import SQLiteFinancialStore
from .trend import TrendScorer


class FinancialRiskPipeline:
    def __init__(self, config_dir: str | Path | None = None):
        load_project_env()
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.configs: AppConfig = load_configs(self.config_dir)
        self.ingestor = CSVIngestor(self.configs.field_map)
        self.preprocessor = DataPreprocessor(self.configs.data_quality)
        self.validator = DataQualityValidator(self.configs.data_quality)
        self.calculator = MetricCalculator()
        self.trend = TrendScorer(self.configs.trend_rules, self.configs.metrics)
        self.scorer = RiskScorer(self.configs)
        self.rules = HardRuleEngine(self.configs.hard_rules)
        self.registry = ModelRegistry()
        self.baostock = BaoStockCollector(self.configs.baostock)
        self.reference: IndustryReferenceModel | None = None

    def prepare(self, input_path: str | Path, output_dir: str | Path, allow_errors: bool = False) -> dict[str, Any]:
        prepared = self._prepare(input_path)
        self.validator.assert_ready(prepared["quality_summary"], allow_errors)
        manifest = self._manifest(input_path, "prepare", len(prepared["records"]), len(prepared["issues"]), {"quality": prepared["quality_summary"], "revision_count": len(prepared["lineage"])})
        ResultWriter(output_dir).write_prepared_bundle(prepared["records"], prepared["issues"], prepared["lineage"], manifest, prepared["quality_summary"])
        return {"manifest": manifest, "quality_issues": prepared["issues"], "quality_summary": prepared["quality_summary"]}

    def baostock_health_check(self) -> dict[str, Any]:
        return self.baostock.health_check()

    def collect_baostock(self, start_year: int, end_year: int, output_dir: str | Path, codes: list[str], database_path: str | Path) -> dict[str, Any]:
        manifest, financials = self.baostock.collect(start_year, end_year, output_dir, codes)
        manifest["database"] = SQLiteFinancialStore(database_path).upsert_financials(financials, "baostock", manifest)
        Path(output_dir, "collection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def database_company_reports(self, database_path: str | Path, ts_code: str) -> list[dict[str, Any]]:
        return SQLiteFinancialStore(database_path).company_reports(ts_code)

    def train(self, input_path: str | Path, model_dir: str | Path, as_of_date: str | None = None, allow_errors: bool = False) -> dict[str, Any]:
        prepared = self._prepare(input_path, as_of_date)
        self.validator.assert_ready(prepared["quality_summary"], allow_errors)
        records, issues, enriched = prepared["records"], prepared["issues"], prepared["enriched"]
        self.reference = IndustryReferenceModel(minimum_sample_count=int(self.configs.scoring_params["peer"]["minimum_sample_count"])).fit(enriched, {"as_of_date": as_of_date, "record_count": len(enriched)})
        model_dir = Path(model_dir)
        model_path = model_dir / "industry_reference.json"
        self.reference.save(model_path)
        manifest = self._manifest(input_path, "train", len(records), len(issues), {"as_of_date": as_of_date, "quality": prepared["quality_summary"], "excluded_after_cutoff": prepared["excluded_after_cutoff"]})
        ResultWriter(model_dir).write_training_manifest(manifest)
        self.registry.initialize_candidate(model_dir, self.config_dir, manifest)
        return {"manifest": manifest, "quality_issues": issues, "model_path": str(model_path)}

    def assess(self, input_path: str | Path, model_dir: str | Path, output_dir: str | Path, enable_ai: bool = False, allow_errors: bool = False) -> dict[str, Any]:
        model_dir = Path(model_dir)
        reference_path = model_dir / "industry_reference.json"
        if not reference_path.exists():
            raise FileNotFoundError(f"缺少行业基准模型: {reference_path}。请先执行 train。")
        self.reference = IndustryReferenceModel.load(reference_path)
        prepared = self._prepare(input_path)
        self.validator.assert_ready(prepared["quality_summary"], allow_errors)
        records, issues, enriched = prepared["records"], prepared["issues"], prepared["enriched"]
        assessments = [self.scorer.assess(record, self.reference) for record in enriched]
        provider = build_provider(self.configs.ai, enable_ai, model_dir / "ai_cache")
        for assessment in assessments:
            assessment["versions"] = self._versions()
            assessment["ai"] = provider.explain(assessment)
        manifest = self._manifest(input_path, "assess", len(records), len(issues), {"quality": prepared["quality_summary"]})
        ResultWriter(output_dir).write_assessment_bundle(assessments, issues, manifest)
        return {"manifest": manifest, "assessments": assessments, "quality_issues": issues}

    def _prepare(self, input_path: str | Path, as_of_date: str | None = None) -> dict[str, Any]:
        raw = self.ingestor.read(input_path)
        normalized, normalization_issues = self.preprocessor.normalize(raw)
        records, revision_issues, lineage = self.preprocessor.canonicalize_revisions(normalized)
        excluded_after_cutoff = 0
        if as_of_date:
            records, excluded_after_cutoff = self._filter_as_of(records, as_of_date)
        records, validation_issues = self.validator.validate(records)
        issues = normalization_issues + revision_issues + validation_issues
        enriched = self.trend.transform(self.calculator.transform(records))
        enriched = [{**record, "rule_triggers": self.rules.evaluate(record)} for record in enriched]
        return {"records": records, "issues": issues, "enriched": enriched, "lineage": lineage, "quality_summary": self.validator.summary(records, issues), "excluded_after_cutoff": excluded_after_cutoff}

    @staticmethod
    def _filter_as_of(records: list[Record], as_of_date: str) -> tuple[list[Record], int]:
        cutoff = str(as_of_date)
        included = [record for record in records if record.get("ann_date") and str(record["ann_date"]) <= cutoff]
        return included, len(records) - len(included)

    def _versions(self) -> dict[str, str]:
        return {**self.configs.versions(), "reference": self.reference.version if self.reference else "unknown"}

    def _manifest(self, input_path: str | Path, mode: str, record_count: int, issue_count: int, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_manifest(input_path, mode, record_count, issue_count, self._versions(), metadata)
