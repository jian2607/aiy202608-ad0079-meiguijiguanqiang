from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.config import DevelopmentConfig  # noqa: E402


class TestConfig(DevelopmentConfig):
    TESTING = True


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_root = Path(self.temporary_directory.name)
        database = temporary_root / "financial_risk.sqlite"
        self.config = type("TestConfig", (TestConfig,), {
            "DATABASE_PATH": str(database),
            "UPLOAD_DIR": str(temporary_root / "uploads"),
            "AI_CACHE_DIR": str(temporary_root / "ai_cache"),
        })
        self.app = create_app(self.config)
        container = self.app.extensions["container"]
        prepared = container.assess_report.risk_engine.prepare_csv(str(ROOT / "examples" / "quarterly_import_template.csv"))
        container.repository.upsert_reports(prepared["records"], "test_fixture", {"source": "public_example"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_lists_quarterly_reports_and_assesses_selected_period(self):
        reports = self.client.get("/api/v1/companies/600101.SH/reports")
        self.assertEqual(reports.status_code, 200)
        data = reports.get_json()["data"]
        self.assertTrue(data)
        self.assertTrue(all(item["statement_type"] in {"Q1", "H1", "Q3"} for item in data))

        selected = data[-1]
        response = self.client.post("/api/v1/assessments", json={"company_code": "600101.SH", "report_period": selected["report_period"]})
        self.assertEqual(response.status_code, 201)
        assessment = response.get_json()["data"]
        self.assertEqual(assessment["report_period"], selected["report_period"])
        self.assertEqual(assessment["statement_type"], selected["statement_type"])
        self.assertNotIn("ai", assessment)

    def test_rejects_annual_report_in_upload(self):
        with (ROOT / "examples" / "import_financials.csv").open("rb") as handle:
            response = self.client.post("/api/v1/imports/files", data={"file": (handle, "annual.csv")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"]["code"], "DATA_QUALITY_REJECTED")


if __name__ == "__main__":
    unittest.main()
