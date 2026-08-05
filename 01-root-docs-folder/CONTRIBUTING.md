# 参与贡献

感谢你改进财报风险评估项目。提交修改前，请确认改动仍遵守项目边界：只处理历史数据、标记风险与弱点，不输出公司未来表现预测。

## 本地开发

```powershell
python -m pip install -e .
python -m pip install -r backend/requirements.txt
python -m unittest discover -s tests -v
python -m unittest discover -s backend/tests -v

cd frontend
npm ci
npm run build
```

需要采集Baostock数据时，可额外安装：

```powershell
python -m pip install -e ".[baostock]"
```

## 提交要求

- 评分公式、阈值、权重和硬规则的改动必须附测试，并说明财务口径；
- 新增数据源时必须记录字段映射、单位、缺失指标和替代口径；
- AI输出必须绑定来源或模型既有证据，不能修改确定性评分；
- 不提交 `.env`、真实密钥、本地数据库、原始上传、生成报告或未确认可再分发的数据；
- 前端改动应通过 `npm run build`，Python改动应通过两组单元测试。

## Pull Request说明

请在PR中写明修改目的、模块边界、验证结果和可能影响的数据口径。涉及用户界面时可附脱敏截图；涉及安全问题时请遵循 `SECURITY.md`，不要创建公开Issue。
