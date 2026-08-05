"""历史行业参考分布：分位数、Median和MAD，并支持分层样本回退。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .interfaces import EMPTY_PEER_STATS, PeerStats, Record
from .utils import median_and_mad, percentile_rank


class IndustryReferenceModel:
    VERSION = "robust-reference.2"

    def __init__(self, payload: dict[str, Any] | None = None, minimum_sample_count: int = 30):
        self.minimum_sample_count = minimum_sample_count
        self.payload: dict[str, Any] = payload or {"version": self.VERSION, "groups": {}, "global": {}, "metadata": {}}

    @staticmethod
    def group_keys(record: Record) -> list[tuple[str, str]]:
        industry = str(record.get("industry") or "未知行业")
        company_type = str(record.get("comp_type") or "一般企业")
        board = str(record.get("board") or "未知板块")
        return [
            (f"{industry}|{company_type}|{board}", "industry_company_type_board"),
            (f"{industry}|{company_type}|*", "industry_company_type"),
            (f"{industry}|*|*", "industry"),
        ]

    def fit(self, enriched_records: list[Record], metadata: dict[str, Any] | None = None) -> "IndustryReferenceModel":
        groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        global_metrics: dict[str, list[float]] = defaultdict(list)
        for record in enriched_records:
            for key, _ in self.group_keys(record):
                for metric, value in record["metrics"].items():
                    if value is not None:
                        groups[key][metric].append(value)
            for metric, value in record["metrics"].items():
                if value is not None:
                    global_metrics[metric].append(value)
        self.payload = {
            "version": self.VERSION,
            "minimum_sample_count": self.minimum_sample_count,
            "groups": {key: self._summarize(metrics) for key, metrics in groups.items()},
            "global": self._summarize(global_metrics),
            "metadata": metadata or {},
        }
        return self

    @staticmethod
    def _summarize(metrics: dict[str, list[float]]) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        for name, values in metrics.items():
            sorted_values = sorted(values)
            centre, mad = median_and_mad(sorted_values)
            summary[name] = {"values": sorted_values, "sample_count": len(sorted_values), "median": centre, "mad": mad}
        return summary

    def describe(self, record: Record, metric: str, value: float) -> PeerStats:
        for key, source in self.group_keys(record):
            group = self.payload.get("groups", {}).get(key, {}).get(metric)
            if group and group.get("sample_count", 0) >= self.minimum_sample_count:
                return self._describe(group, value, source)
        group = self.payload.get("global", {}).get(metric)
        if not group:
            return dict(EMPTY_PEER_STATS)
        return self._describe(group, value, "global")

    def _describe(self, group: dict[str, Any], value: float, source: str) -> PeerStats:
        values = group["values"]
        return {"sample_count": group["sample_count"], "percentile": percentile_rank(values, value), "robust_z": self._robust_z(group, value), "source": source}

    @staticmethod
    def _robust_z(group: dict[str, Any], value: float) -> float | None:
        if group["sample_count"] < 3 or group["mad"] is None or group["mad"] < 1e-12:
            return 0.0 if group["sample_count"] >= 3 else None
        return (value - group["median"]) / (1.4826 * group["mad"])

    @property
    def version(self) -> str:
        return self.payload.get("version", "unknown")

    def save(self, path: str | Path) -> None:
        import json
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "IndustryReferenceModel":
        import json
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload, int(payload.get("minimum_sample_count", 30)))
