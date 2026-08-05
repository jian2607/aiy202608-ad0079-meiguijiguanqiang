from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..errors import NotFoundError


class CompanyWebReviewService:
    """Starts a bounded background web-review run for an existing assessment."""

    def __init__(self, repository, agent):
        self.repository = repository
        self.agent = agent
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="web-review")

    def start(self, assessment_id: str) -> dict:
        assessment = self.repository.get_assessment(assessment_id)
        if not assessment:
            raise NotFoundError("未找到风险评估结果", {"assessment_id": assessment_id})
        run = self.repository.get_or_create_web_review(assessment, self.agent.prompt_version)
        if run["status"] == "queued":
            self.executor.submit(self._run, run["run_id"], assessment)
        return run

    def get(self, run_id: str) -> dict:
        run = self.repository.get_web_review(run_id)
        if not run:
            raise NotFoundError("未找到联网审查任务", {"run_id": run_id})
        return run

    def _run(self, run_id: str, assessment: dict) -> None:
        self.repository.mark_web_review_running(run_id)
        try:
            self.repository.complete_web_review(run_id, self.agent.review(assessment))
        except Exception as error:  # the financial score remains available when web review fails
            self.repository.fail_web_review(run_id, str(error) or type(error).__name__)
