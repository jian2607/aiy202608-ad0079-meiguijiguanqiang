from __future__ import annotations

from ..errors import NotFoundError, ValidationError


class AssessReportService:
    def __init__(self, repository, risk_engine):
        self.repository = repository
        self.risk_engine = risk_engine

    def execute(self, command):
        reports = self.repository.list_reports(command.company_code)
        selected = [item for item in reports if item["report_period"] == command.report_period]
        if not selected:
            raise NotFoundError("未找到指定报告期", {"company_code": command.company_code, "report_period": command.report_period})
        if selected[0]["statement_type"] not in {"Q1", "H1", "Q3"}:
            raise ValidationError("系统仅支持Q1、H1和Q3季度报告")
        history = [report for report in reports if report["report_period"] <= command.report_period]
        assessment = self.risk_engine.assess(history)
        if assessment["report_period"] != command.report_period:
            raise ValidationError("报告历史排序异常，无法定位目标报告期")
        return self.repository.save_assessment(assessment)
