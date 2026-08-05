"""基于SQLite的公司财务档案库；保留财报更正版本并提供按公司/年份的当前视图。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..utils import utc_now


class SQLiteFinancialStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS companies (
                    ts_code TEXT PRIMARY KEY,
                    company_name TEXT,
                    industry TEXT,
                    board TEXT,
                    comp_type TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS report_revisions (
                    ts_code TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    ann_date TEXT NOT NULL,
                    report_year INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    PRIMARY KEY (ts_code, report_period, ann_date, source)
                );
                CREATE TABLE IF NOT EXISTS financial_reports (
                    ts_code TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    ann_date TEXT NOT NULL,
                    report_year INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (ts_code, report_period)
                );
                CREATE INDEX IF NOT EXISTS idx_financial_reports_company_year
                    ON financial_reports (ts_code, report_year, report_period);
                CREATE TABLE IF NOT EXISTS collection_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    manifest_json TEXT NOT NULL
                );
                CREATE VIEW IF NOT EXISTS company_reports_by_year AS
                    SELECT c.ts_code, c.company_name, c.industry, c.board, c.comp_type,
                           r.report_year, r.report_period, r.ann_date, r.source, r.payload_json
                    FROM financial_reports r
                    LEFT JOIN companies c ON c.ts_code = r.ts_code
                    ORDER BY c.ts_code, r.report_year, r.report_period;
            """)

    def upsert_financials(self, records: list[dict[str, Any]], source: str, manifest: dict[str, Any]) -> dict[str, int]:
        self.initialize()
        inserted, updated = 0, 0
        now = utc_now()
        with self._connection() as connection:
            for record in records:
                ts_code, period, ann_date = str(record.get("ts_code") or ""), str(record.get("report_period") or ""), str(record.get("ann_date") or "")
                if not ts_code or not period or not ann_date:
                    continue
                year = int(period[:4])
                payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
                connection.execute("""
                    INSERT INTO companies(ts_code, company_name, industry, board, comp_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ts_code) DO UPDATE SET company_name=excluded.company_name, industry=excluded.industry, board=excluded.board, comp_type=excluded.comp_type, updated_at=excluded.updated_at
                """, (ts_code, record.get("company_name"), record.get("industry"), record.get("board"), record.get("comp_type"), now))
                connection.execute("""
                    INSERT OR REPLACE INTO report_revisions(ts_code, report_period, ann_date, report_year, source, payload_json, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, period, ann_date, year, source, payload, now))
                current = connection.execute("SELECT ann_date, payload_json FROM financial_reports WHERE ts_code=? AND report_period=?", (ts_code, period)).fetchone()
                if current is None:
                    inserted += 1
                elif ann_date > str(current[0]):
                    updated += 1
                elif ann_date == str(current[0]) and payload != str(current[1]):
                    updated += 1
                else:
                    continue
                connection.execute("""
                    INSERT INTO financial_reports(ts_code, report_period, ann_date, report_year, source, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ts_code, report_period) DO UPDATE SET ann_date=excluded.ann_date, report_year=excluded.report_year, source=excluded.source, payload_json=excluded.payload_json, updated_at=excluded.updated_at
                """, (ts_code, period, ann_date, year, source, payload, now))
            connection.execute("INSERT INTO collection_runs(source, collected_at, record_count, manifest_json) VALUES (?, ?, ?, ?)", (source, now, inserted + updated, json.dumps(manifest, ensure_ascii=False)))
        return {"inserted": inserted, "updated": updated, "database": str(self.path)}

    def company_reports(self, ts_code: str) -> list[dict[str, Any]]:
        self.initialize()
        with self._connection() as connection:
            rows = connection.execute("SELECT report_year, report_period, ann_date, payload_json FROM financial_reports WHERE ts_code=? ORDER BY report_year, report_period", (ts_code,)).fetchall()
        return [{"report_year": row[0], "report_period": row[1], "ann_date": row[2], **json.loads(row[3])} for row in rows]

    def summary(self) -> dict[str, int]:
        self.initialize()
        with self._connection() as connection:
            companies = connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            reports = connection.execute("SELECT COUNT(*) FROM financial_reports").fetchone()[0]
            revisions = connection.execute("SELECT COUNT(*) FROM report_revisions").fetchone()[0]
        return {"companies": companies, "current_reports": reports, "report_revisions": revisions}

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
