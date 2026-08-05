from __future__ import annotations

from flask import Blueprint, current_app, request

from ...schemas.assessment import AssessmentCommand
from ...schemas.common import success


api_v1 = Blueprint("api_v1", __name__)


def container():
    return current_app.extensions["container"]


@api_v1.get("/health")
def health():
    return success({"status": "ok", "storage": container().repository.summary()})


@api_v1.get("/companies")
def list_companies():
    return success(container().company_queries.list_companies(request.args.get("q")))


@api_v1.get("/companies/<company_code>/reports")
def list_reports(company_code: str):
    return success(container().company_queries.list_reports(company_code))


@api_v1.post("/imports/files")
def import_file():
    return success(container().import_reports.execute(request.files.get("file")), 201)


@api_v1.post("/assessments")
def assess_report():
    command = AssessmentCommand.from_payload(request.get_json(silent=True))
    return success(container().assess_report.execute(command), 201)


@api_v1.get("/assessments/<assessment_id>")
def get_assessment(assessment_id: str):
    assessment = container().repository.get_assessment(assessment_id)
    if assessment is None:
        from ...errors import NotFoundError
        raise NotFoundError("未找到风险评估结果", {"assessment_id": assessment_id})
    return success(assessment)


@api_v1.post("/assessments/<assessment_id>/web-review")
def start_web_review(assessment_id: str):
    return success(container().web_reviews.start(assessment_id), 202)


@api_v1.get("/web-reviews/<run_id>")
def get_web_review(run_id: str):
    return success(container().web_reviews.get(run_id))
