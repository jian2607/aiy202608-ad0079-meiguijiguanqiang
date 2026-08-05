from __future__ import annotations

from dataclasses import dataclass

from ..errors import ValidationError


@dataclass(frozen=True)
class AssessmentCommand:
    company_code: str
    report_period: str

    @classmethod
    def from_payload(cls, payload: dict | None) -> "AssessmentCommand":
        payload = payload or {}
        company_code = str(payload.get("company_code") or "").strip()
        report_period = str(payload.get("report_period") or "").strip()
        if not company_code or not report_period:
            raise ValidationError("company_code和report_period为必填项")
        return cls(company_code=company_code, report_period=report_period)
