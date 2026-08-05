from __future__ import annotations

from ..errors import NotFoundError


class CompanyQueryService:
    def __init__(self, repository):
        self.repository = repository

    def list_companies(self, query: str | None = None):
        return self.repository.list_companies(query)

    def list_reports(self, company_code: str):
        reports = self.repository.list_reports(company_code)
        if not reports:
            raise NotFoundError("未找到该公司的季度报告", {"company_code": company_code})
        return reports
