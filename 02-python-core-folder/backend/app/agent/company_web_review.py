from __future__ import annotations

from datetime import date
from typing import Any

from .deepseek_client import DeepSeekAgentClient
from .search_provider import BingNewsRssSearchProvider, SearchResult, restrict_to_window


class CompanyWebReviewAgent:
    """Produces source-bound company findings for one financial-report window."""

    prompt_version = "company-web-review.2"

    def __init__(self, model: DeepSeekAgentClient, search: BingNewsRssSearchProvider):
        self.model = model
        self.search = search

    def review(self, assessment: dict[str, Any]) -> dict[str, Any]:
        window_start, window_end = _report_window(assessment["report_period"], assessment["ann_date"])
        context = {
            "company_name": assessment["company_name"],
            "company_code": assessment["ts_code"],
            "report_period": assessment["report_period"],
            "announcement_date": assessment["ann_date"],
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
        }
        queries = self._queries(context)
        results: list[SearchResult] = []
        successful_searches = 0
        for query in queries:
            try:
                results.extend(self.search.search(query))
                successful_searches += 1
            except Exception:
                # A single unstable search must not discard results returned by
                # the remaining queries. If every query fails, surface a real
                # task failure instead of reporting a misleading empty result.
                continue
        if not successful_searches:
            raise RuntimeError("news_search_unavailable")
        sources = restrict_to_window(results, window_start, window_end)
        if not sources:
            return {"prompt_version": self.prompt_version, "queries": queries, "sources": [], "findings": []}
        findings = self._findings(context, sources)
        return {"prompt_version": self.prompt_version, "queries": queries, "sources": [_source(item) for item in sources], "findings": findings}

    def _queries(self, context: dict[str, str]) -> list[str]:
        fallback = _fallback_queries(context)
        try:
            planned = self.model.json_response(self.model.prompt("search_planner_v1.md"), context, max_tokens=320)
        except Exception:
            planned = {}
        values = planned.get("queries", []) if isinstance(planned, dict) else []
        company_name = context["company_name"]
        plain_code = context["company_code"].split(".", 1)[0]
        valid = []
        for value in values:
            if not isinstance(value, str) or company_name not in value:
                continue
            query = value.strip().replace(context["company_code"], plain_code)
            if query:
                valid.append(query)
        # The bare company name is deliberately first. Free news providers
        # often return nothing for an over-constrained name+code+year query.
        return list(dict.fromkeys([*fallback[:1], *valid, *fallback[1:]]))[:4]

    def _findings(self, context: dict[str, str], sources: list[SearchResult]) -> list[dict[str, Any]]:
        payload = {**context, "sources": [_source(item) for item in sources]}
        result = self.model.json_response(self.model.prompt("evidence_analyzer_v1.md"), payload, max_tokens=1200)
        requested = result.get("findings", []) if isinstance(result, dict) else []
        lookup = {item.source_id: item for item in sources}
        accepted: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in requested:
            if not isinstance(item, dict) or len(accepted) >= 6:
                continue
            source = lookup.get(str(item.get("source_id", "")))
            finding_type = item.get("type")
            category = item.get("category")
            excerpt = str(item.get("excerpt", "")).strip()
            title = str(item.get("title", "")).strip()
            analysis = str(item.get("analysis", "")).strip()
            if not source or finding_type not in {"risk", "positive"} or not category or not excerpt or not title or not analysis:
                continue
            evidence = f"{source.title} {source.snippet}"
            if excerpt not in evidence:
                continue
            key = (finding_type, title)
            if key in seen:
                continue
            seen.add(key)
            accepted.append({
                "source_id": source.source_id,
                "type": finding_type,
                "category": category,
                "severity": item.get("severity") if item.get("severity") in {"low", "medium", "high"} else "low",
                "title": title[:120],
                "excerpt": excerpt[:300],
                "analysis": analysis[:360],
                "confidence": _confidence(item.get("confidence")),
            })
        return accepted


def _report_window(report_period: str, ann_date: str) -> tuple[date, date]:
    period = date.fromisoformat(report_period)
    announcement = date.fromisoformat(ann_date)
    return date(period.year, 1, 1), min(announcement, date.today())


def _fallback_queries(context: dict[str, str]) -> list[str]:
    company_name = context["company_name"]
    return [
        company_name,
        f"{company_name} 监管 风险",
        f"{company_name} 经营 进展",
    ]


def _source(item: SearchResult) -> dict[str, str | None]:
    return {"source_id": item.source_id, "title": item.title, "url": item.url, "publisher": item.publisher, "published_at": item.published_at, "snippet": item.snippet, "query": item.query}


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5
