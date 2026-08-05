from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.company_web_review import CompanyWebReviewAgent  # noqa: E402
from app.agent.search_provider import SearchResult  # noqa: E402


class FakeModel:
    def prompt(self, name: str) -> str:
        return name

    def json_response(self, system_prompt: str, payload: dict, max_tokens: int) -> dict:
        if system_prompt == "search_planner_v1.md":
            return {"queries": [f"{payload['company_name']} {payload['company_code']} 监管 风险"]}
        return {"findings": [{
            "source_id": "source-1", "type": "risk", "category": "regulatory", "severity": "medium",
            "title": "监管关注", "excerpt": "收到监管关注", "analysis": "该事件应纳入风险复核。", "confidence": 0.91,
        }]}


class FakeSearch:
    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        return [
            SearchResult("source-1", "监管关注", "https://example.com/a", "示例来源", "2025-05-15", "公司收到监管关注", query),
            SearchResult("source-2", "过期事件", "https://example.com/b", "示例来源", "2024-01-01", "公司历史事项", query),
        ]


class CompanyWebReviewAgentTests(unittest.TestCase):
    def test_uses_bare_company_name_and_removes_exchange_suffix(self):
        agent = CompanyWebReviewAgent(FakeModel(), FakeSearch())
        queries = agent._queries({
            "company_name": "测试公司",
            "company_code": "000001.SZ",
            "report_period": "2025-03-31",
            "ann_date": "2025-05-20",
        })
        self.assertEqual(queries[0], "测试公司")
        self.assertTrue(any("000001" in query for query in queries[1:]))
        self.assertTrue(all(".SZ" not in query for query in queries))

    def test_keeps_only_source_bound_findings_inside_report_window(self):
        agent = CompanyWebReviewAgent(FakeModel(), FakeSearch())
        result = agent.review({"company_name": "测试公司", "ts_code": "000001.SZ", "report_period": "2025-03-31", "ann_date": "2025-05-20"})
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["excerpt"], "收到监管关注")


if __name__ == "__main__":
    unittest.main()
