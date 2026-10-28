# 财报风险侦察员

> **项目已停止维护**：本仓库仅保留作参赛记录与公开展示，后续不再提供更新或技术支持。当前版本不保证可直接运行，文档及依赖可能已过时。

> 帮助财报研究用户快速整理历史财务数据，定位风险与薄弱环节，并用AI补充带来源的同期公开信息。

🏆 **AIY 黑客松 2026 深圳站**参赛作品  
🏷 命题企业 / 赛道：金稳院  
👤 团队：meiguijiguanqiang  
🔢 团队编号：**AD0079**

它不预测ST、退市或股价。它根据已导入数据输出财务风险强度、风险标签、证据和数据质量，并由AI Agent补充带来源的同期公开信息。

## 👥 团队分工

| 成员 | 负责 |
| --- | --- |
| 万江钰 | 风险模型、后端开发 |
| 刘昱辰 | 前端界面、交互设计 |
| 范俊宇 | 用户调研、ppt制作 |
| 曾凡枫 | 数据采集、市场调研 |
| 吴静雯 | 项目分析、方案设计、资源对接 |

## 🎬 演示

项目支持现场完整演示：导入财报、选择公司与报告期、查看可解释风险评分，再查看AI联网审查生成的带来源新闻证据。

- 本地访问：`http://localhost:5173`

### 风险评分与指标证据

![风险评分与指标证据](<docs/images/屏幕截图 2026-08-05 203218.png>)

### AI联网审查与来源

![AI联网审查与来源](<docs/images/屏幕截图 2026-08-05 203209.png>)

## 特点

- 核心风险模型使用Python标准库实现，Web应用依赖Flask与React；
- 指标、权重、阈值、共振规则、审计分级和硬性风险规则均配置化；
- 通过历史数据训练行业参考分布（分位数、Median、MAD）；
- 自动标准化日期与金额单位，按公告日期处理财报更正版本；
- 正式训练和评估均有数据质量门槛、公告截止日和版本状态；
- 所有输出带有模型、规则和数据版本信息。

## 快速开始

```powershell
python -m financial_risk prepare --input examples/historical_financials.csv --output data/prepared_demo
python -m financial_risk train --input data/prepared_demo/prepared_financials.csv --model-dir artifacts/baseline_2026_01 --as-of-date 2026-06-30
python -m financial_risk assess --input examples/import_financials.csv --model-dir artifacts/baseline_2026_01 --output output/assessment_2026_01
python -m financial_risk promote --model-dir artifacts/baseline_2026_01 --status approved --note "数据与规则复核通过"
```

训练会生成行业基准文件；评估会生成：

- `risk_assessments.json`：完整风险证据；
- `risk_summary.csv`：一行一家公司/报告期的汇总；
- `data_quality.json`：数据质量问题；
- `manifest.json`：输入、规则和模型版本。

`prepare` 会额外生成 `prepared_financials.csv`、`revision_lineage.json` 和 `quality_summary.json`。若存在严重错误或核心字段完整率不足，正式运行会停止；仅供排查时可显式增加 `--allow-errors`。

## 人工复核与校准

模型不会把自己的结果直接用于自我训练。请先生成人工复核表，再基于已填写结果生成校准建议：

```powershell
python -m financial_risk review-template --assessment output/assessment_2026_01/risk_assessments.json --output reviews/review_2026_01.csv
python -m financial_risk calibrate --reviews reviews/review_2026_01.csv --output output/calibration_2026_01
```

校准报告只提出阈值、硬规则或指标覆盖范围的复核建议，不会自动修改正式配置。
```

AI仅接收已经计算出的指标、风险标签和证据，不能修改风险分或原始财务数据。

DeepSeek调用会自动采用75秒超时、最多3次指数退避重试，并缓存已成功结果。再次执行相同数据时，仅会请求此前失败或新增的记录。

## 本地密钥

项目根目录的 `.env` 用于存放本机的 `DEEPSEEK_API_KEY`；程序启动时自动读取，已设置的系统环境变量优先。该文件已被 `.gitignore` 忽略，不要上传、发送或填写到公开文档中。

数据采集本身不需要任何密钥：Baostock为免费公开接口，无需注册或Token。

公开部署或参与开发时，请先复制 `.env.example` 为 `.env`，只在本机填写密钥。仓库不包含任何可用密钥；如果密钥曾出现在提交、日志、截图或聊天记录中，应立即在服务商后台轮换，而不是只删除文件。

## 公开仓库的数据边界

仓库只保留源码、配置、脱敏示例数据以及应用启动所需的 `artifacts/industry_reference.json`。以下内容仅保存在本机，不进入版本控制：

- `.env` 与其他密钥文件；
- `data/` 下的SQLite数据库、上传文件和Baostock采集结果；
- `output/`、`reviews/`、日志、AI缓存和生成的训练基线；
- 前端依赖目录与构建产物。

Baostock采集结果由使用者在本地通过接口重新生成。使用、再分发或公开第三方数据前，应自行核对对应数据源和新闻来源的许可条款。安全问题请按 `SECURITY.md` 私下报告，不要在公开Issue中粘贴密钥或未脱敏财务数据。

## AI 联网审查

风险分析页会对每一份已生成的评估自动创建一个联网审查任务。该任务使用 Bing 新闻 RSS 检索公开新闻元数据，并使用 `deepseek-v4-flash` 生成带来源的风险或积极进展摘要。它是独立的信息补充Agent，不是评分引擎的复核者。

- 检索时间严格限制在报告年度开始日至该报告公告日；不在窗口内的信息不会展示。
- 只保存标题、日期、来源、摘要和链接；不抓取或保存文章全文。
- 每项发现都必须引用搜索结果中的原始摘要；没有有效发现时，前端明确显示“AI未找到有用新闻”。
- 联网审查不修改财务风险分；网络或模型不可用时，基础风险评估照常运行。
- `.env` 中需要配置 `DEEPSEEK_API_KEY`；后端会读取该变量但不会向前端返回密钥。

## Baostock 数据采集

Baostock为免费公开接口，无需注册或Token。先安装SDK并检查连通性：

```powershell
python -m pip install baostock
python -m financial_risk baostock-check
```

采集内置十家非金融公司样本池2021—2025年的季度财务指标，并写入本地SQLite数据库：

```powershell
python -m financial_risk collect-baostock `
  --start-year 2021 `
  --end-year 2025 `
  --output "data\baostock_sample_2021_2025" `
  --database "data\financial_risk.sqlite" `
  --default-sample
```

内置样本为贵州茅台、五粮液、伊利股份、美的集团、格力电器、三一重工、比亚迪、宁德时代、恒瑞医药和海康威视。数据库同时保留原始公告修订版本，并以“公司代码—报告期”保存当前有效版本；按公司查询：

```powershell
python -m financial_risk database-company --database "data\financial_risk.sqlite" --ts-code 600519.SH
```

采集输出 `baostock_quarterly_financials.csv` 与 `collection_manifest.json`，后者记录本次采集使用的全部替代口径、不可得指标与不可评分维度。再执行 `prepare` 进入模型标准数据层。

### 数据口径与替代方案

模型只处理一季报、中报、三季报（12月31日年报不在Baostock季频接口的处理范围内）。以下指标没有直接字段，由适配器按明确的数学等价关系换算：

| 模型指标 | 来源与换算 |
| --- | --- |
| `interest_coverage` | 现金流量接口的 `ebitToInterest`（已获利息倍数，不在偿债能力接口） |
| `ocf_net_profit_ratio` | 现金流量接口的 `CFOToNP`（经营性现金净流量/净利润） |
| `receivable_revenue_ratio` | 应收账款周转天数 `NRTurnDays` ÷ 365，等价于应收账款/年化营业收入 |
| `revenue_growth` | 接口不提供营收同比，由同一报表类型的上一期 `MBRevenue` 计算同比 |
| `revenue` / `net_profit` | 盈利能力接口的 `MBRevenue`、`netProfit`，供硬性规则使用 |

`revenue` 采用主营营业收入，与营业收入总额存在口径差异，用于阈值判断时须注意。

百分数字段（`gpMargin`、`npMargin`、`roeAvg`、`YOY` 系列）按字段既定口径固定除以100，不按数值大小启发式判断——净利率1.2%与120%在启发式下无法区分。

Baostock文档对 `netProfit` 与 `MBRevenue` 的单位存在“元”与“万元”两种表述。单位由 `baostock.json` 的 `amount_unit` 声明（默认“元”），并由采集器对营业收入量级做主动核对，异常记录写入 `collection_manifest.json` 的 `magnitude_warnings`。首次采集后请检查该字段。

### 不做替代的项目

以下项目在Baostock免费接口中没有数学上站得住脚的代理，模型标记为不可得，不用其他口径伪造：

- `goodwill_equity_ratio`（商誉/净资产）：接口既无商誉也无净资产绝对值。减值维度（权重0.15）因此永久不可评分，已在 `baostock.json` 的 `unscorable_groups` 中显式登记；剩余三个维度权重合计0.85，高于总覆盖率门槛0.6，总分按比例归一化后照常生成。
- `cash_short_debt_ratio`（现金短债比）：接口的 `cashRatio` 分母是流动负债而非短期债务，口径不同，仅作为 `supplementary_cash_ratio` 供人工复核参考，不参与评分。
- `deducted_net_profit_margin`（扣非净利率）：接口不提供扣非净利润。
- 审计意见与ST历史：接口不提供任何文本类财报附注。`scoring_params.json` 中依赖审计意见的风险下限规则在本数据源下不会触发。

硬性规则 `FIN_002`（净资产为负）需要净资产绝对值，在本数据源下改由等价条件 `FIN_003`（资产负债率>100%）覆盖。`FIN_001` 的1亿元营收阈值按年度口径校准，已限定只在年报（FY）上评估；季报口径由 `FIN_004` 以三季度等比折算的7500万元阈值近似覆盖，该规则强制人工复核。

## 配置

模型代码和配置统一位于 `financial_risk/`：

- `financial_risk/config/metric_rules.json`：指标阈值和插值锚点；
- `financial_risk/config/weights.json`：维度和指标权重；
- `financial_risk/config/scoring_params.json`：同行比较、融合、下限和可信度；
- `financial_risk/config/trend_rules.json`：趋势恶化规则；
- `financial_risk/config/data_quality.json`：必填字段、完整率与质量阻断门槛；
- `financial_risk/config/hard_rules.json`：可审计的财务硬性规则；
- `financial_risk/config/ai_deepseek.json`：DeepSeek V4 Flash连接配置；
- `financial_risk/config/baostock.json`：数据源口径、金额单位、不可得指标与不可评分维度登记。

`hard_rules.json` 中的规则是内部风险标记规则，不应直接当作交易所现行监管结论；带“需人工复核”的结论必须由研究人员核验。

详见 `docs/architecture.md`。
## Web 应用

项目已提供模块化的 Flask 后端与 React 前端：

```text
financial_risk/   独立风险模型核心
backend/          Flask API、应用服务与适配器
frontend/         React页面、功能模块与公共UI
```

启动后端：

```powershell
python -m pip install -r backend\requirements.txt
python backend\run.py
```

启动前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。前端仅调用 `/api/v1`，DeepSeek密钥只由根目录 `.env` 中的后端进程读取。

## 🛠 用到的技术 / AI工具

- Python、Flask：风险模型、数据处理和API服务；
- React、TypeScript、Vite：Web交互界面；
- SQLite：本地财报、评估结果和AI来源记录；
- Baostock：免费公开财务数据接口；
- DeepSeek V4 Flash：搜索规划和有来源的新闻证据分析；
- GitHub Actions：自动运行模型测试、API测试和前端构建。

## 🚀 后续计划

- 增加更多合规新闻搜索来源，降低单一来源遗漏；
- 增加脱敏演示数据和一键启动脚本；
- 扩充行业参考样本，并持续通过人工复核校准规则；
- 在保持“不预测、不荐股”的前提下增强风险解释与审计追踪。

## 使用限制与免责声明

本项目用于历史财务数据处理、风险弱点标记和研究辅助，不构成投资建议、评级结论或监管认定。风险分是配置化内部指标，不代表公司发生违约、ST、退市或价格变化的概率。联网Agent的结果来自第三方公开摘要，可能存在遗漏、延迟或错误；重要结论必须回到原始公告、财报和权威来源人工核验。

## 📄 版权与许可

本作品版权归README“团队分工”中列出的真实参与成员共同所有，采用 [MIT License](./LICENSE) 开源，使用请署名。

> 本项目为AIY黑客松参赛作品，作品归团队所有；AIY组委会仅作收录与展示。
