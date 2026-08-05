import { Link } from "react-router-dom";
import { HomeCarousel } from "../../widgets/home-carousel/HomeCarousel";

export function HomePage() {
  return <div className="home-scroll">
    <section className="home-snap home-carousel-snap"><HomeCarousel /></section>
    <section className="home-poster-grid">
      <Poster index="01" title="季度数据入库" text="导入 Q1、H1、Q3 财报 CSV，完成字段、日期、单位、缺失值和重复版本检查后再按公司与报告期归档。" to="/import" action="导入财报" />
      <Poster index="02" title="公司财报索引" text="用公司名称或代码定位本地数据，查看各报告期及公告日期，并从指定报告直接进入风险分析。" to="/companies" action="浏览公司财报" />
      <Poster index="03" title="可解释风险评估" text="以财务指标、硬规则和风险共振形成分数账单，同时展示覆盖率、触发原因与原始指标依据。" to="/analysis" action="查看风险分析" />
      <Poster index="04" title="AI 联网证据" text="按财报对应时间窗口检索公开信息；DeepSeek 只整理附有来源的风险或积极进展，没有可靠发现时不展示。" to="/analysis" action="进入联网审查" />
    </section>
  </div>;
}

function Poster({ index, title, text, action, to }: { index: string; title: string; text: string; action: string; to: string }) {
  return <article className="poster-card"><span>{index}</span><h2>{title}</h2><p>{text}</p><Link to={to}>{action} →</Link></article>;
}
