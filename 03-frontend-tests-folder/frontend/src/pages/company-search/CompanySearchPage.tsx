import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCompanies, listReports } from "../../entities/assessment/api/assessmentApi";
import type { Company } from "../../entities/assessment/model/types";

export function CompanySearchPage() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Company | null>(null);
  const navigate = useNavigate();
  const companies = useQuery({ queryKey: ["companies", query], queryFn: () => listCompanies(query) });
  const reports = useQuery({ queryKey: ["reports", selected?.company_code], queryFn: () => listReports(selected!.company_code), enabled: Boolean(selected) });
  return <div><PageHead title="公司财报" sub="按公司代码或名称查找，并选择Q1、H1或Q3报告。" /><div className="search-layout scout-search"><section><label className="searchbar"><input value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索公司名称或代码" /><span>{companies.data?.length ?? 0} 家</span></label>
    <div className="company-list scout-company-list">{companies.isLoading ? <p className="empty">正在加载公司库…</p> : companies.data?.map(company => <div key={company.company_code}><button className={`company-row ${selected?.company_code === company.company_code ? "selected" : ""}`} onClick={() => setSelected(selected?.company_code === company.company_code ? null : company)}><i className="status-dot" /><span><strong>{company.company_name}</strong><small>{company.company_code} · {company.industry ?? "未分类"}</small></span><span>{company.report_count}期报告</span><b>⌄</b></button>{selected?.company_code === company.company_code && <div className="period-list">{reports.isLoading ? <span>正在读取报告期…</span> : reports.data?.map(report => <button key={report.report_period} onClick={() => navigate(`/analysis?code=${encodeURIComponent(selected.company_code)}&period=${report.report_period}`)}><span>{report.statement_type} · {report.report_period}</span><small>公告 {report.ann_date}</small><b>查看 →</b></button>)}</div>}</div>)}</div></section>
    <aside className="az-index" aria-label="首字母索引">{"ABCDEFGHJKLMNPQRSTWXYZ".split("").map(letter => <span key={letter}>{letter}</span>)}</aside></div></div>;
}

export function PageHead({ title, sub }: { title: string; sub: string }) { return <header className="page-head"><div><h1>{title}</h1><p>{sub}</p></div></header>; }
