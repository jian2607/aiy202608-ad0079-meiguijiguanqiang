"""人工复核模板与校准建议；只报告差异，不自动篡改正式评分配置。"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .utils import utc_now


REVIEW_FIELDS = [
    "ts_code", "company_name", "report_period", "model_risk_score", "model_risk_level",
    "data_confidence", "risk_floor_reasons", "review_risk_level", "confirmed_reasons",
    "false_positive", "missed_risk", "reviewer", "review_date", "notes",
]


class ReviewWorkflow:
    def create_template(self, assessment_path: str | Path, output_path: str | Path) -> int:
        assessments = json.loads(Path(assessment_path).read_text(encoding="utf-8"))
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            for item in assessments:
                writer.writerow({
                    "ts_code": item.get("ts_code"), "company_name": item.get("company_name"),
                    "report_period": item.get("report_period"), "model_risk_score": item.get("risk_score"),
                    "model_risk_level": item.get("risk_level"),
                    "data_confidence": item.get("data_confidence", {}).get("score"),
                    "risk_floor_reasons": "；".join(item.get("risk_floor", {}).get("reasons", [])),
                })
        return len(assessments)

    def calibrate(self, reviews_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
        with Path(reviews_path).open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        reviewed = [row for row in rows if str(row.get("review_risk_level") or "").strip()]
        false_positive = [row for row in reviewed if self._truthy(row.get("false_positive"))]
        missed_risk = [row for row in reviewed if self._truthy(row.get("missed_risk"))]
        agreements = [row for row in reviewed if row.get("model_risk_level") == row.get("review_risk_level")]
        by_level: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "false_positive": 0, "missed_risk": 0})
        for row in reviewed:
            bucket = by_level[str(row.get("model_risk_level") or "未标注")]
            bucket["reviewed"] += 1
            bucket["false_positive"] += int(self._truthy(row.get("false_positive")))
            bucket["missed_risk"] += int(self._truthy(row.get("missed_risk")))
        report = {
            "created_at": utc_now(), "reviewed_count": len(reviewed), "total_template_rows": len(rows),
            "agreement_rate": round(len(agreements) / len(reviewed), 4) if reviewed else None,
            "false_positive_count": len(false_positive), "missed_risk_count": len(missed_risk),
            "by_model_risk_level": dict(by_level), "suggestions": self._suggest(len(reviewed), len(false_positive), len(missed_risk)),
            "automatic_config_change": False,
        }
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "calibration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    @staticmethod
    def _truthy(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "是", "y"}

    @staticmethod
    def _suggest(reviewed: int, false_positive: int, missed_risk: int) -> list[str]:
        if reviewed < 30:
            return ["已复核样本少于30条，仅供定性参考，暂不建议调整正式阈值或权重。"]
        suggestions = []
        if false_positive / reviewed > 0.3:
            suggestions.append("误报率超过30%，请优先复核硬规则、审计意见分级和共振加分的适用范围。")
        if missed_risk:
            suggestions.append("存在漏标样本，请整理确认原因并评估新增指标、趋势规则或人工复核项。")
        return suggestions or ["当前复核样本未显示明显系统性偏差；继续积累分行业复核样本。"]
