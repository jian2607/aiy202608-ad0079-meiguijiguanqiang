# 模块化架构

模型的全部实现与默认配置均位于 `financial_risk/`：

```text
financial_risk/
├─ config/             唯一配置来源
├─ preprocessing/      日期、单位、报表类型与财报更正处理
├─ sources/             标准数据接口适配器（当前为Baostock季频免费接口）
├─ storage/             SQLite本地公司财务档案库
├─ scoring/            风险评分子包
├─ interfaces.py        模块协议
├─ ingestion.py         导入与字段映射
├─ quality.py           数据质量校验
├─ metrics.py           财务公式
├─ trend.py             历史趋势评分
├─ reference.py         行业基准训练与查询
├─ rules.py             配置驱动的硬性风险规则
├─ registry.py          模型候选、发布状态与配置快照
├─ review.py            人工复核模板与校准建议
├─ ai.py                DeepSeek与空AI提供方
├─ reporting.py         JSON/CSV/清单输出
├─ pipeline.py          模块编排
└─ cli.py               命令行入口
```

依赖方向为：

```text
cli → pipeline → ingestion / preprocessing / quality / metrics / trend / rules / reference / scoring / ai / reporting
                     ↓
                  registry / interfaces / curves / utils / config
```

评分层不依赖数据源、文件格式或AI；AI服务不可用时，核心风险评估照常完成。

## 修改入口

| 修改内容 | 文件 |
|---|---|
| 指标风险区间 | `financial_risk/config/metric_rules.json` |
| 权重 | `financial_risk/config/weights.json` |
| 趋势阈值 | `financial_risk/config/trend_rules.json` |
| 同行、共振、下限、可信度 | `financial_risk/config/scoring_params.json` |
| 风险共振组合 | `financial_risk/config/synergy_rules.json` |
| DeepSeek模型、超时、重试 | `financial_risk/config/ai_deepseek.json` |
| 数据质量门槛 | `financial_risk/config/data_quality.json` |
| 财务硬性风险规则 | `financial_risk/config/hard_rules.json` |
| 公式 | `financial_risk/metrics.py` |
| 指标特殊状态 | `financial_risk/scoring/overrides.py` |
| 新增AI供应商 | `financial_risk/ai.py` 的 `PROVIDERS` |
| 新增输出格式 | `financial_risk/reporting.py` |

训练版本会在模型目录保存 `config_snapshot/` 与 `release_status.json`。行业基准按“行业+企业类型+板块 → 行业+企业类型 → 行业 → 全市场”逐级回退；训练可指定公告截止日，防止截止日后的数据进入该版本。

AI输出须绑定已有指标证据；无法绑定证据的摘要、标签和复核项会被丢弃。AI从不参与分数计算。

Baostock适配器只经由其公开季频接口取数，无需Token。原始接口响应和合并财务表写在模型包外的数据目录，以免原始数据与模型代码混杂。

适配器承担全部口径换算责任：百分数字段按字段既定口径固定除以100（不按数值大小启发式判断），金额单位由 `baostock.json` 的 `amount_unit` 声明并交由 `preprocessing` 统一换算。数据源无法提供的指标在 `baostock.json` 的 `unavailable_metrics` 中登记；若某维度因此永久无法达到 `minimum_coverage`，必须在 `unscorable_groups` 中显式登记，否则 `load_configs` 会直接报错，避免维度长期静默返回 `insufficient_data`。

SQLite库包含 `companies`、`report_revisions`、`financial_reports` 和 `collection_runs`：同一公司同一报告期的最新公告版本进入 `financial_reports`，全部公告修订版本保留在 `report_revisions`。索引与视图按公司代码、报告年份和报告期排序。

## Web应用与联网Agent

Web应用保持端口与适配器分离，风险模型不依赖Flask、SQLite实现或前端：

```text
frontend/src/
├─ pages/              页面编排与路由入口
├─ widgets/            可复用业务视图
├─ entities/           评估实体、类型与API调用
└─ shared/             HTTP客户端与公共样式

backend/app/
├─ api/v1/             HTTP路由与请求响应转换
├─ application/        导入、查询、评估、联网审查用例
├─ ports/              仓库和外部能力接口
├─ adapters/           SQLite与核心风险引擎适配器
├─ agent/              检索、DeepSeek调用与证据约束
└─ schemas/            API数据结构
```

风险评估路径为 `API → application → risk engine adapter → financial_risk`。联网审查路径为 `API → application → CompanyWebReviewAgent → SearchProvider / DeepSeekAgentClient`。两条路径只通过评估ID和结构化事实关联；Agent不能回写风险分、指标值或规则结果。

检索供应商和模型客户端均封装在 `backend/app/agent/`，提示词位于 `backend/prompts/company_web_review/`。替换搜索服务或模型时不需要修改评分核心、API响应结构或前端发现卡片。
