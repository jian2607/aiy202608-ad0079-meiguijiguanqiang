from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from financial_risk.storage import SQLiteFinancialStore


def statement_type_for_period(report_period: str) -> str | None:
    suffixes = {"03-31": "Q1", "06-30": "H1", "09-30": "Q3"}
    return suffixes.get(str(report_period)[5:])


class SQLiteRepository:
    """Application persistence adapter; raw financial storage remains owned by financial_risk."""

    def __init__(self, database_path: str | Path):
        self.path = Path(database_path)
        self.financial_store = SQLiteFinancialStore(self.path)
        self.initialize()

    def initialize(self) -> None:
        self.financial_store.initialize()
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS app_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    ts_code TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(ts_code, report_period)
                );
                CREATE INDEX IF NOT EXISTS idx_app_assessments_company_period
                    ON app_assessments(ts_code, report_period);
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    assessment_id TEXT NOT NULL UNIQUE,
                    ts_code TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS web_sources (
                    source_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    publisher TEXT,
                    published_at TEXT,
                    snippet TEXT NOT NULL,
                    query_text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_findings (
                    finding_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    finding_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    confidence REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agent_runs_assessment ON agent_runs(assessment_id);
                CREATE INDEX IF NOT EXISTS idx_web_sources_run ON web_sources(run_id);
                CREATE INDEX IF NOT EXISTS idx_agent_findings_run ON agent_findings(run_id);
            """)

    def list_companies(self, query: str | None = None) -> list[dict[str, Any]]:
        normalized = (query or "").strip()
        with self._connection() as connection:
            if normalized:
                rows = connection.execute("""
                    SELECT c.ts_code, c.company_name, c.industry, c.board, COUNT(r.report_period)
                    FROM companies c LEFT JOIN financial_reports r ON c.ts_code=r.ts_code
                    WHERE c.ts_code LIKE ? OR c.company_name LIKE ?
                    GROUP BY c.ts_code ORDER BY c.company_name COLLATE NOCASE
                """, (f"%{normalized}%", f"%{normalized}%")).fetchall()
            else:
                rows = connection.execute("""
                    SELECT c.ts_code, c.company_name, c.industry, c.board, COUNT(r.report_period)
                    FROM companies c LEFT JOIN financial_reports r ON c.ts_code=r.ts_code
                    GROUP BY c.ts_code ORDER BY c.company_name COLLATE NOCASE
                """).fetchall()
        return [{"company_code": row[0], "company_name": row[1] or row[0], "industry": row[2], "board": row[3], "report_count": row[4]} for row in rows]

    def list_reports(self, company_code: str) -> list[dict[str, Any]]:
        reports = self.financial_store.company_reports(company_code)
        normalized = []
        for report in reports:
            statement_type = report.get("statement_type") or statement_type_for_period(report["report_period"])
            if statement_type:
                normalized.append({**report, "statement_type": statement_type})
        return sorted(normalized, key=lambda item: item["report_period"])

    def get_report(self, company_code: str, report_period: str) -> dict[str, Any] | None:
        return next((report for report in self.list_reports(company_code) if report["report_period"] == report_period), None)

    def upsert_reports(self, records: list[dict[str, Any]], source: str, manifest: dict[str, Any]) -> dict[str, int]:
        return self.financial_store.upsert_financials(records, source, manifest)

    def save_assessment(self, assessment: dict[str, Any]) -> dict[str, Any]:
        assessment_id = f"asm_{uuid4().hex[:16]}"
        payload = {**assessment, "assessment_id": assessment_id}
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as connection:
            existing = connection.execute("SELECT assessment_id FROM app_assessments WHERE ts_code=? AND report_period=?", (payload["ts_code"], payload["report_period"])).fetchone()
            if existing:
                assessment_id = existing[0]
                payload["assessment_id"] = assessment_id
            connection.execute("""
                INSERT INTO app_assessments(assessment_id, ts_code, report_period, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ts_code, report_period) DO UPDATE SET payload_json=excluded.payload_json, created_at=excluded.created_at
            """, (assessment_id, payload["ts_code"], payload["report_period"], json.dumps(payload, ensure_ascii=False), now))
        return payload

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT payload_json FROM app_assessments WHERE assessment_id=?", (assessment_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_or_create_web_review(self, assessment: dict[str, Any], prompt_version: str) -> dict[str, Any]:
        with self._connection() as connection:
            existing = connection.execute("SELECT run_id, status, prompt_version FROM agent_runs WHERE assessment_id=?", (assessment["assessment_id"],)).fetchone()
            if existing:
                should_restart = existing[1] == "failed" or existing[2] != prompt_version
                if should_restart:
                    connection.execute("DELETE FROM agent_findings WHERE run_id=?", (existing[0],))
                    connection.execute("DELETE FROM web_sources WHERE run_id=?", (existing[0],))
                    connection.execute("""
                        UPDATE agent_runs
                        SET status='queued', prompt_version=?, created_at=?, completed_at=NULL, error_reason=NULL
                        WHERE run_id=?
                    """, (prompt_version, datetime.now(timezone.utc).isoformat(), existing[0]))
                return self._web_review(connection, existing[0])
            run_id = f"wr_{uuid4().hex[:16]}"
            connection.execute("""
                INSERT INTO agent_runs(run_id, assessment_id, ts_code, report_period, company_name, status, prompt_version, created_at)
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
            """, (run_id, assessment["assessment_id"], assessment["ts_code"], assessment["report_period"], assessment["company_name"], prompt_version, datetime.now(timezone.utc).isoformat()))
            return self._web_review(connection, run_id)

    def get_web_review(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT run_id FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
            return self._web_review(connection, run_id) if row else None

    def mark_web_review_running(self, run_id: str) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE agent_runs SET status='running', error_reason=NULL WHERE run_id=?", (run_id,))

    def complete_web_review(self, run_id: str, result: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM agent_findings WHERE run_id=?", (run_id,))
            connection.execute("DELETE FROM web_sources WHERE run_id=?", (run_id,))
            source_ids: dict[str, str] = {}
            for source in result.get("sources", []):
                source_id = f"{run_id}_{source['source_id']}"
                source_ids[source["source_id"]] = source_id
                connection.execute("""
                    INSERT INTO web_sources(source_id, run_id, title, url, publisher, published_at, snippet, query_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (source_id, run_id, source["title"], source["url"], source.get("publisher"), source.get("published_at"), source["snippet"], source["query"]))
            for finding in result.get("findings", []):
                source_id = source_ids.get(finding["source_id"])
                if not source_id:
                    continue
                connection.execute("""
                    INSERT INTO agent_findings(finding_id, run_id, source_id, finding_type, category, severity, title, excerpt, analysis, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (f"finding_{uuid4().hex[:16]}", run_id, source_id, finding["type"], finding["category"], finding["severity"], finding["title"], finding["excerpt"], finding["analysis"], finding["confidence"]))
            connection.execute("UPDATE agent_runs SET status='completed', completed_at=?, error_reason=NULL WHERE run_id=?", (datetime.now(timezone.utc).isoformat(), run_id))

    def fail_web_review(self, run_id: str, reason: str) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE agent_runs SET status='failed', completed_at=?, error_reason=? WHERE run_id=?", (datetime.now(timezone.utc).isoformat(), reason[:200], run_id))

    def summary(self) -> dict[str, int]:
        return self.financial_store.summary()

    def _web_review(self, connection: sqlite3.Connection, run_id: str) -> dict[str, Any]:
        run = connection.execute("""
            SELECT run_id, assessment_id, ts_code, report_period, company_name, status, prompt_version, created_at, completed_at, error_reason
            FROM agent_runs WHERE run_id=?
        """, (run_id,)).fetchone()
        sources = connection.execute("""
            SELECT source_id, title, url, publisher, published_at, snippet, query_text
            FROM web_sources WHERE run_id=? ORDER BY published_at DESC, source_id
        """, (run_id,)).fetchall()
        findings = connection.execute("""
            SELECT f.finding_id, f.finding_type, f.category, f.severity, f.title, f.excerpt, f.analysis, f.confidence,
                   s.url, s.publisher, s.published_at
            FROM agent_findings f JOIN web_sources s ON s.source_id=f.source_id
            WHERE f.run_id=? ORDER BY f.confidence DESC, f.finding_id
        """, (run_id,)).fetchall()
        return {
            "run_id": run[0], "assessment_id": run[1], "company_code": run[2], "report_period": run[3], "company_name": run[4],
            "status": run[5], "prompt_version": run[6], "created_at": run[7], "completed_at": run[8], "reason": run[9],
            "sources": [{"source_id": row[0], "title": row[1], "url": row[2], "publisher": row[3], "published_at": row[4], "snippet": row[5], "query": row[6]} for row in sources],
            "findings": [{"finding_id": row[0], "type": row[1], "category": row[2], "severity": row[3], "title": row[4], "excerpt": row[5], "analysis": row[6], "confidence": row[7], "source_url": row[8], "source_name": row[9], "published_at": row[10]} for row in findings],
        }

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
