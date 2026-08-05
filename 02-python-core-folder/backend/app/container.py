from __future__ import annotations

from dataclasses import dataclass

from .adapters import FinancialRiskEngineAdapter, SQLiteRepository
from .agent import BingNewsRssSearchProvider, CompanyWebReviewAgent, DeepSeekAgentClient
from .application import AssessReportService, CompanyQueryService, CompanyWebReviewService, ImportReportService


@dataclass(frozen=True)
class Container:
    company_queries: CompanyQueryService
    assess_report: AssessReportService
    import_reports: ImportReportService
    web_reviews: CompanyWebReviewService
    repository: SQLiteRepository


def build_container(config) -> Container:
    repository = SQLiteRepository(config["DATABASE_PATH"])
    engine = FinancialRiskEngineAdapter(config["MODEL_DIR"])
    agent = CompanyWebReviewAgent(
        DeepSeekAgentClient(config["AGENT_PROMPT_DIR"]),
        BingNewsRssSearchProvider(config["AGENT_SEARCH_TIMEOUT_SECONDS"]),
    )
    return Container(
        company_queries=CompanyQueryService(repository),
        assess_report=AssessReportService(repository, engine),
        import_reports=ImportReportService(repository, engine, config["UPLOAD_DIR"]),
        web_reviews=CompanyWebReviewService(repository, agent),
        repository=repository,
    )
