"""CSV读取与字段规范化。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .utils import as_float


IDENTIFIER_FIELDS = {
    "ts_code", "company_name", "industry", "board", "comp_type", "report_period",
    "ann_date", "audit_opinion", "amount_unit", "statement_type", "data_source",
}


class CSVIngestor:
    def __init__(self, field_mapping: dict[str, str]):
        self.field_mapping = field_mapping

    def read(self, path: str | Path) -> list[dict[str, Any]]:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        return self.normalize(rows)

    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in rows:
            row: dict[str, Any] = {}
            for source_name, value in raw.items():
                canonical_name = self.field_mapping.get(source_name.strip(), source_name.strip())
                if canonical_name in IDENTIFIER_FIELDS:
                    row[canonical_name] = str(value).strip() if value is not None else ""
                else:
                    row[canonical_name] = as_float(value)
            normalized.append(row)
        return normalized
