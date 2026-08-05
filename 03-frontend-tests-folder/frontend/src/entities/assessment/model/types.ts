export type Company = { company_code: string; company_name: string; industry: string | null; board: string | null; report_count: number };
export type QuarterlyReport = { report_period: string; ann_date: string; statement_type: "Q1" | "H1" | "Q3"; company_name?: string; industry?: string };
export type Metric = { label: string; value: number | null; score: number | null; absolute_score: number; peer_score: number; trend_score: number; evidence: string; status: string };
export type Assessment = {
  assessment_id: string;
  ts_code: string;
  company_name: string;
  report_period: string;
  ann_date: string;
  statement_type: string;
  risk_score: number;
  base_score?: number | null;
  computed_score?: number | null;
  risk_level: string;
  data_confidence: { score: number; level: string; metric_completeness: number };
  dimensions: Record<string, { score: number | null; coverage: number; status: string }>;
  metrics: Record<string, Metric>;
  synergy: { addition: number; triggered: Array<{ id: string; label: string; addition: number }> };
  risk_floor: { score: number; reasons: string[] };
  base_coverage?: number;
  versions: Record<string, string>;
};

export type WebFinding = {
  finding_id: string;
  type: "risk" | "positive";
  category: string;
  severity: "low" | "medium" | "high";
  title: string;
  excerpt: string;
  analysis: string;
  confidence: number;
  source_url: string;
  source_name: string | null;
  published_at: string | null;
};

export type WebReview = {
  run_id: string;
  assessment_id: string;
  company_code: string;
  report_period: string;
  company_name: string;
  status: "queued" | "running" | "completed" | "failed";
  prompt_version: string;
  created_at: string;
  completed_at: string | null;
  reason: string | null;
  findings: WebFinding[];
};
