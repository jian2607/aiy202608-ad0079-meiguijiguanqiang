import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { createAssessment, getWebReview, listCompanies, listReports, startWebReview } from "../../entities/assessment/api/assessmentApi";
import type { Assessment } from "../../entities/assessment/model/types";
import { MetricMatrix } from "../../widgets/metric-matrix/MetricMatrix";
import { RiskOverview } from "../../widgets/risk-overview/RiskOverview";
import { ScoreBill } from "../../widgets/score-bill/ScoreBill";
import { WebFindings, WebReviewNotice } from "../../widgets/web-findings/WebFindings";
import { PageHead } from "../company-search/CompanySearchPage";

type Direction = "next" | "previous";

export function RiskAnalysisPage() {
  const [params, setParams] = useSearchParams();
  const [assessmentCache, setAssessmentCache] = useState<Record<string, Assessment>>({});
  const [direction, setDirection] = useState<Direction>("next");
  const [webReviewRunId, setWebReviewRunId] = useState<string | null>(null);
  const companyCode = params.get("code") ?? "600519.SH";
  const companies = useQuery({ queryKey: ["companies", "analysis-picker"], queryFn: () => listCompanies("") });
  const reports = useQuery({ queryKey: ["reports", companyCode], queryFn: () => listReports(companyCode) });
  const reportPeriod = params.get("period") ?? reports.data?.[reports.data.length - 1]?.report_period ?? "";
  const assessmentKey = `${companyCode}:${reportPeriod}`;
  const requested = useRef(new Set<string>());
  const webRequested = useRef(new Set<string>());
  const assess = useMutation({ mutationFn: () => createAssessment(companyCode, reportPeriod), onSuccess: result => {
    setAssessmentCache(cache => ({ ...cache, [`${result.ts_code}:${result.report_period}`]: result }));
  } });
  const webReviewStart = useMutation({ mutationFn: startWebReview, onSuccess: run => setWebReviewRunId(run.run_id) });
  const webReview = useQuery({
    queryKey: ["web-review", webReviewRunId],
    queryFn: () => getWebReview(webReviewRunId!),
    enabled: Boolean(webReviewRunId),
    refetchInterval: query => ["queued", "running"].includes(query.state.data?.status ?? "") ? 1500 : false,
  });
  const assessment = assessmentCache[assessmentKey];
  useEffect(() => {
    if (!reportPeriod || assessment || requested.current.has(assessmentKey)) return;
    requested.current.add(assessmentKey);
    assess.mutate();
  }, [assessment, assessmentKey, assess.mutate, reportPeriod]);
  useEffect(() => {
    if (!assessment || webRequested.current.has(assessment.assessment_id)) return;
    webRequested.current.add(assessment.assessment_id);
    setWebReviewRunId(null);
    webReviewStart.mutate(assessment.assessment_id);
  }, [assessment, webReviewStart.mutate]);

  const reportIndex = reports.data?.findIndex(report => report.report_period === reportPeriod) ?? -1;
  const move = (offset: number) => {
    const next = reports.data?.[reportIndex + offset];
    if (!next) return;
    setDirection(offset > 0 ? "next" : "previous");
    setParams({ code: companyCode, period: next.report_period });
  };
  const selectReport = (period: string) => {
    const nextIndex = reports.data?.findIndex(report => report.report_period === period) ?? reportIndex;
    setDirection(nextIndex >= reportIndex ? "next" : "previous");
    setParams({ code: companyCode, period });
  };
  const selectCompany = (code: string) => { setDirection("next"); setParams({ code }); };
  const webReviewCompleted = webReview.data?.status === "completed" && webReview.data.assessment_id === assessment?.assessment_id;
  const webReviewMatchesAssessment = webReview.data?.assessment_id === assessment?.assessment_id;
  const webReviewLoading = webReviewStart.isPending || (webReviewMatchesAssessment && ["queued", "running"].includes(webReview.data?.status ?? ""));
  const webReviewFailed = webReviewStart.isError || webReview.isError || (webReviewMatchesAssessment && webReview.data?.status === "failed");
  const findings = webReviewCompleted ? (webReview.data?.findings ?? []) : [];
  const retryWebReview = () => {
    if (!assessment || webReviewStart.isPending) return;
    setWebReviewRunId(null);
    webReviewStart.mutate(assessment.assessment_id);
  };
  return <div><PageHead title="风险分析" sub="风险分基于已导入财报；联网审查仅检索报告期至公告日之间的公开信息。" />
    <section className="analysis-pickers" aria-label="选择评估对象"><label>公司<select value={companyCode} onChange={event => selectCompany(event.target.value)} disabled={companies.isLoading}>{companies.data?.map(company => <option key={company.company_code} value={company.company_code}>{company.company_name} · {company.company_code}</option>)}</select></label><label>财报<select value={reportPeriod} onChange={event => selectReport(event.target.value)} disabled={reports.isLoading || !reports.data?.length}>{reports.data?.map(report => <option key={report.report_period} value={report.report_period}>{report.statement_type} · {report.report_period} · 公告 {report.ann_date}</option>)}</select></label><span>{companies.isLoading ? "正在读取已入库公司…" : `已入库 ${companies.data?.length ?? 0} 家公司`}</span></section>
    <div className="analysis-selector"><button type="button" disabled={reportIndex <= 0} onClick={() => move(-1)}>← 上一份</button><div className="report-tabs">{reports.data?.map(report => <button key={report.report_period} className={report.report_period === reportPeriod ? "active" : ""} onClick={() => selectReport(report.report_period)}><i />{report.statement_type} · {report.report_period}</button>)}</div><button type="button" disabled={reportIndex < 0 || reportIndex >= (reports.data?.length ?? 0) - 1} onClick={() => move(1)}>下一份 →</button></div>
    {!assessment && <AssessmentSkeleton failed={assess.isError} message={assess.error?.message} />}
    {assessment && <div className={`assessment-transition ${direction}`} key={assessmentKey}><div className="analysis-layout"><RiskOverview assessment={assessment} /><ScoreBill assessment={assessment} /></div><MetricMatrix assessment={assessment} />{webReviewLoading && <WebReviewNotice state="loading" />}{webReviewFailed && <WebReviewNotice state="failed" onRetry={retryWebReview} />}{webReviewCompleted && <WebFindings findings={findings} />}</div>}
  </div>;
}

function AssessmentSkeleton({ failed, message }: { failed: boolean; message?: string }) {
  if (failed) return <section className="surface empty-action"><p className="error-text">自动评估失败：{message}</p></section>;
  return <div className="assessment-skeleton" aria-live="polite" aria-label="正在生成风险评估"><div className="skeleton-overview" /><div className="skeleton-bill"><i /><i /><i /><i /></div><div className="skeleton-table"><i /><i /><i /><i /><i /></div></div>;
}
