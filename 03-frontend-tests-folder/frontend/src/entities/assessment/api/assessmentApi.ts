import { apiGet, apiPost } from "../../../shared/api/client";
import type { Assessment, Company, QuarterlyReport, WebReview } from "../model/types";

export const listCompanies = (query = "") => apiGet<Company[]>(`/companies${query ? `?q=${encodeURIComponent(query)}` : ""}`);
export const listReports = (companyCode: string) => apiGet<QuarterlyReport[]>(`/companies/${encodeURIComponent(companyCode)}/reports`);
export const createAssessment = (companyCode: string, reportPeriod: string) => apiPost<Assessment>("/assessments", { company_code: companyCode, report_period: reportPeriod });
export const getAssessment = (assessmentId: string) => apiGet<Assessment>(`/assessments/${encodeURIComponent(assessmentId)}`);
export const startWebReview = (assessmentId: string) => apiPost<WebReview>(`/assessments/${encodeURIComponent(assessmentId)}/web-review`);
export const getWebReview = (runId: string) => apiGet<WebReview>(`/web-reviews/${encodeURIComponent(runId)}`);
