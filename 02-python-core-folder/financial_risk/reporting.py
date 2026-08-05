"""所有结果落盘操作；评分和编排模块不认识文件格式细节。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .interfaces import Assessment
from .utils import file_sha256, utc_now


def build_manifest(input_path: str | Path, mode: str, record_count: int, quality_issue_count: int, versions: dict[str, str], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"mode": mode, "created_at": utc_now(), "input_file": str(input_path), "input_sha256": file_sha256(input_path), "record_count": record_count, "quality_issue_count": quality_issue_count, "versions": versions, "metadata": metadata or {}}


class ResultWriter:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_training_manifest(self, manifest: dict[str, Any]) -> None:
        self._json("training_manifest.json", manifest)

    def write_prepared_bundle(self, records: list[dict[str, Any]], issues: list[dict[str, Any]], lineage: list[dict[str, Any]], manifest: dict[str, Any], quality_summary: dict[str, Any]) -> None:
        self._records_csv("prepared_financials.csv", records)
        self._json("data_quality.json", issues)
        self._json("quality_summary.json", quality_summary)
        self._json("revision_lineage.json", lineage)
        self._json("prepare_manifest.json", manifest)

    def write_assessment_bundle(self, assessments: list[Assessment], issues: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
        self._json("risk_assessments.json", assessments)
        self._json("data_quality.json", issues)
        self._json("manifest.json", manifest)
        self._summary(assessments)

    def _json(self, name: str, data: Any) -> None:
        (self.output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _summary(self, assessments: list[Assessment]) -> None:
        fields = ["ts_code", "company_name", "report_period", "risk_score", "risk_level", "data_confidence", "solvency_risk", "profit_quality_risk", "operations_risk", "impairment_risk", "synergy_addition", "risk_floor"]
        with (self.output_dir / "risk_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for result in assessments:
                dimensions = result["dimensions"]
                writer.writerow({
                    "ts_code": result["ts_code"], "company_name": result["company_name"], "report_period": result["report_period"], "risk_score": result["risk_score"], "risk_level": result["risk_level"], "data_confidence": result["data_confidence"]["score"],
                    "solvency_risk": dimensions["solvency"]["score"], "profit_quality_risk": dimensions["profit_quality"]["score"], "operations_risk": dimensions["operations"]["score"], "impairment_risk": dimensions["impairment"]["score"],
                    "synergy_addition": result["synergy"]["addition"], "risk_floor": result["risk_floor"]["score"],
                })

    def _records_csv(self, name: str, records: list[dict[str, Any]]) -> None:
        fieldnames = sorted({key for record in records for key in record if key not in {"metrics", "calculation_notes", "trend_scores", "rule_triggers"}})
        with (self.output_dir / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
