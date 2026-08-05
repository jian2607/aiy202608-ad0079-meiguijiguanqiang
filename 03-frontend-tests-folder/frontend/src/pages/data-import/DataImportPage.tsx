import { useState } from "react";
import { apiUpload } from "../../shared/api/client";
import { PageHead } from "../company-search/CompanySearchPage";

type ImportResult = { file_name: string; accepted_count: number; rejected_non_quarter_count: number; quality_summary: { errors: number; warnings: number } };

export function DataImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit() {
    if (!file) return;
    setLoading(true); setError(null);
    try { setResult(await apiUpload<ImportResult>("/imports/files", file)); } catch (reason) { setError(reason instanceof Error ? reason.message : "导入失败"); } finally { setLoading(false); }
  }
  return <div><PageHead title="导入财报" sub="当前版本支持CSV；Q1、H1和Q3以外的记录不会进入评分。" /><div className="import-layout"><section className="surface upload-zone scout-drop"><h2>选择财报文件</h2><p className="muted">上传后先执行字段、日期、单位和重复版本检查。</p><input type="file" accept=".csv" onChange={event => setFile(event.target.files?.[0] ?? null)} /><div className="format-tags"><span>CSV</span><span>Q1</span><span>H1</span><span>Q3</span></div><p>{file ? `已选择：${file.name}` : "尚未选择文件"}</p><button className="primary-action" disabled={!file || loading} onClick={submit}>{loading ? "正在检查与导入…" : "开始导入"}</button>{error && <p className="error-text">{error}</p>}{result && <div className="import-result">已导入 {result.accepted_count} 条季度记录；拒绝非季度记录 {result.rejected_non_quarter_count} 条；错误 {result.quality_summary.errors}，警告 {result.quality_summary.warnings}。</div>}</section><aside className="surface steps"><Step n="1" title="识别结构" text="读取公司代码、报告期和公告日期。" /><Step n="2" title="质量检查" text="检查缺失值、单位与历史更正。" /><Step n="3" title="确认入库" text="只保存通过检查的季度记录。" /><Step n="4" title="执行评估" text="在公司页面选择报告后生成风险结果。" /></aside></div></div>;
}

function Step({ n, title, text }: { n: string; title: string; text: string }) { return <div className="step"><b>{n}</b><div><strong>{title}</strong><p>{text}</p></div></div>; }
