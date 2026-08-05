from __future__ import annotations

from typing import Any


class DimensionAggregator:
    def __init__(self, groups: dict[str, Any], params: dict[str, Any]):
        self.groups, self.minimum_total_coverage = groups, float(params["minimum_total_coverage"])

    def by_dimension(self, details: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for name, group in self.groups.items():
            available = [(metric, weight) for metric, weight in group["metrics"].items() if details[metric]["score"] is not None]
            coverage = sum(weight for _, weight in available)
            if coverage < group["minimum_coverage"]:
                result[name] = {"score": None, "coverage": round(coverage, 4), "status": "insufficient_data"}
            else:
                result[name] = {"score": round(sum(details[m]["score"] * w for m, w in available) / coverage, 2), "coverage": round(coverage, 4), "status": "available"}
        return result

    def total(self, dimensions: dict[str, Any]) -> tuple[float | None, float]:
        available = [(name, group["weight"]) for name, group in self.groups.items() if dimensions[name]["score"] is not None]
        coverage = sum(weight for _, weight in available)
        if coverage < self.minimum_total_coverage:
            return None, coverage
        return sum(dimensions[name]["score"] * weight for name, weight in available) / coverage, coverage
