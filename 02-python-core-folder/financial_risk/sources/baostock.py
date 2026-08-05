"""Baostock季度财务指标适配器（免费、无Token）。

字段口径依据Baostock官方季频接口定义：

- ``query_profit_data``：roeAvg、npMargin、gpMargin为小数比率；netProfit、MBRevenue为金额。
- ``query_operation_data``：NRTurnDays、INVTurnDays为“季报天数/周转率”，已按期间归一，
  可直接与年度口径的周转天数阈值比较。
- ``query_balance_data``：currentRatio、quickRatio、cashRatio、liabilityToAsset为小数比率。
- ``query_cash_flow_data``：ebitToInterest为倍数；CFOToNP、CFOToOR、CFOToGr为小数比率。
  注意已获利息倍数位于现金流量接口，不在偿债能力接口。
- ``query_growth_data``：YOY系列均为小数比率，且不提供营业收入同比增长率。

营业收入同比增长率不从接口直接读取，而由MetricCalculator依据同一报表类型的上一期
营业收入自行计算，因此本适配器只负责提供营业收入与净利润的金额。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..utils import utc_now


class BaoStockError(RuntimeError):
    pass


class BaoStockCollector:
    """将Baostock的季度指标映射为风险模型可直接评分的标准指标。"""

    QUERIES = {
        "profit": "query_profit_data",
        "operation": "query_operation_data",
        "growth": "query_growth_data",
        "balance": "query_balance_data",
        "cashflow": "query_cash_flow_data",
    }
    #: 一个自然年的天数，用于把周转天数换算为“应收账款/年化营业收入”。
    DAYS_PER_YEAR = 365.0

    def __init__(self, config: dict[str, Any], module: Any | None = None):
        self.config = config
        self.module = module

    def health_check(self) -> dict[str, Any]:
        module = self._module()
        login = module.login()
        try:
            self._assert_result(login, "login")
            return {"status": "ok", "provider": "baostock"}
        finally:
            module.logout()

    def collect(self, start_year: int, end_year: int, output_dir: str | Path, codes: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if start_year > end_year:
            raise ValueError("start_year 不能晚于 end_year")
        module = self._module()
        login = module.login()
        self._assert_result(login, "login")
        try:
            records: list[dict[str, Any]] = []
            for code in codes:
                for year in range(start_year, end_year + 1):
                    for quarter in self.config["allowed_quarters"]:
                        records.extend(self._collect_quarter(module, code, year, quarter))
        finally:
            module.logout()
        records.sort(key=lambda row: (str(row.get("ts_code") or ""), str(row.get("report_period") or "")))
        magnitude_warnings = self._check_amount_magnitude(records)
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        self._write_csv(root / "baostock_quarterly_financials.csv", records)
        manifest = {
            "created_at": utc_now(),
            "provider": "baostock",
            "frequency": "quarterly",
            "years": [start_year, end_year],
            "company_codes": codes,
            "company_count": len(codes),
            "financial_record_count": len(records),
            "amount_unit": self.config["amount_unit"],
            "files": {"financials": "baostock_quarterly_financials.csv"},
            "unavailable_metrics": list(self.config.get("unavailable_metrics", [])),
            "unscorable_groups": list(self.config.get("unscorable_groups", [])),
            "substitutions": [
                "receivable_revenue_ratio 由应收账款周转天数除以365换算，等价于应收账款/年化营业收入。",
                "ocf_net_profit_ratio 直接采用现金流量接口的CFOToNP（经营性现金净流量/净利润）。",
                "interest_coverage 采用现金流量接口的ebitToInterest（已获利息倍数）。",
                "revenue 采用主营营业收入MBRevenue，与营业收入总额存在口径差异。",
                "revenue_growth 不由接口提供，改由同一报表类型的上一期营业收入计算同比。",
            ],
            "limitations": [
                "Baostock适配器采用公开的季频财务指标，不等同于完整三大表原始科目。",
                "商誉、净资产绝对值、扣非净利润、现金短债比与审计意见无可靠来源，不做代理替换。",
                "季度现金流与中报、三季报的累计口径须按同季度跨年比较。",
            ],
            "magnitude_warnings": magnitude_warnings,
        }
        (root / "collection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest, records

    def _collect_quarter(self, module: Any, code: str, year: int, quarter: int) -> list[dict[str, Any]]:
        result_sets = {name: self._rows(getattr(module, method)(code=code, year=year, quarter=quarter), method) for name, method in self.QUERIES.items()}
        indexed = {name: self._index(rows) for name, rows in result_sets.items()}
        keys = set().union(*(set(rows) for rows in indexed.values()))
        records = []
        for key in keys:
            profit, operation = indexed["profit"].get(key, {}), indexed["operation"].get(key, {})
            growth, balance = indexed["growth"].get(key, {}), indexed["balance"].get(key, {})
            cashflow = indexed["cashflow"].get(key, {})
            sources = (profit, operation, growth, balance, cashflow)
            stat_date = self._field(sources, "statDate")
            if not stat_date:
                continue
            code_value = str(self._field(sources, "code") or code)
            metadata = self.config.get("sample_metadata", {}).get(code_value, {})
            receivable_days = self._number(operation.get("NRTurnDays"))
            records.append({
                "ts_code": self._ts_code(code_value),
                "company_name": metadata.get("name", ""),
                "industry": metadata.get("industry", ""),
                "board": metadata.get("board", ""),
                "comp_type": "一般企业",
                "report_period": stat_date,
                "ann_date": self._field(sources, "pubDate"),
                "data_source": self.config["data_source"],
                "amount_unit": self.config["amount_unit"],
                # 参与评分的标准指标
                "debt_ratio": self._debt_ratio(balance),
                "current_ratio": self._number(balance.get("currentRatio")),
                "quick_ratio": self._number(balance.get("quickRatio")),
                "interest_coverage": self._number(cashflow.get("ebitToInterest")),
                "gross_margin": self._ratio(profit.get("gpMargin")),
                "net_margin": self._ratio(profit.get("npMargin")),
                "ocf_net_profit_ratio": self._number(cashflow.get("CFOToNP")),
                "receivable_days": receivable_days,
                "inventory_days": self._number(operation.get("INVTurnDays")),
                "receivable_revenue_ratio": receivable_days / self.DAYS_PER_YEAR if receivable_days is not None else None,
                # 金额字段：供硬性规则与营收同比使用
                "revenue": self._number(profit.get("MBRevenue")),
                "net_profit": self._number(profit.get("netProfit")),
                # 补充上下文字段：不参与评分，仅用于人工复核
                "supplementary_roe_avg": self._ratio(profit.get("roeAvg")),
                "supplementary_cash_ratio": self._number(balance.get("cashRatio")),
                "supplementary_asset_to_equity": self._number(balance.get("assetToEquity")),
                "supplementary_source_liability_to_asset": self._number(balance.get("liabilityToAsset")),
                "supplementary_cfo_to_revenue": self._number(cashflow.get("CFOToOR")),
                "supplementary_tangible_asset_ratio": self._number(cashflow.get("tangibleAssetToAsset")),
                "supplementary_net_profit_yoy": self._ratio(growth.get("YOYNI")),
                "supplementary_asset_turnover": self._number(operation.get("AssetTurnRatio")),
            })
        return records

    def _check_amount_magnitude(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """核对营业收入量级是否与配置的amount_unit一致。

        Baostock文档对netProfit与MBRevenue的单位表述存在“元”与“万元”两种说法，
        单位配错会直接影响以绝对金额为条件的硬性规则，因此这里主动比对而不是默认正确。
        """
        threshold = self.config.get("revenue_magnitude_warning_threshold")
        if not threshold:
            return []
        warnings = []
        for record in records:
            revenue = record.get("revenue")
            if revenue is not None and 0 < revenue < float(threshold):
                warnings.append({
                    "ts_code": record["ts_code"],
                    "report_period": record["report_period"],
                    "revenue": revenue,
                    "amount_unit": record["amount_unit"],
                    "message": f"营业收入低于量级告警阈值{threshold}，请确认amount_unit配置是否与接口实际单位一致",
                })
        return warnings

    def _module(self) -> Any:
        if self.module is not None:
            return self.module
        try:
            import baostock  # type: ignore[import-not-found]
            return baostock
        except ImportError as error:
            raise BaoStockError("未安装baostock。请执行：python -m pip install baostock") from error

    @staticmethod
    def _rows(result: Any, operation: str) -> list[dict[str, Any]]:
        BaoStockCollector._assert_result(result, operation)
        rows = []
        while result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        return rows

    @staticmethod
    def _assert_result(result: Any, operation: str) -> None:
        if str(getattr(result, "error_code", "-1")) != "0":
            raise BaoStockError(f"{operation} 失败：{getattr(result, 'error_msg', '未知错误')}")

    @staticmethod
    def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        return {(str(row.get("code") or ""), str(row.get("statDate") or "")): row for row in rows if row.get("statDate")}

    @staticmethod
    def _field(rows: tuple[dict[str, Any], ...], field: str) -> Any:
        for row in rows:
            if row.get(field) not in (None, ""):
                return row[field]
        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "", "None") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ratio(value: Any) -> float | None:
        """返回 Baostock 已按小数口径提供的比例字段。"""
        return BaoStockCollector._number(value)

    @classmethod
    def _debt_ratio(cls, balance: dict[str, Any]) -> float | None:
        """优先依据资产/权益比反推资产负债率，规避来源字段的量级异常。"""
        asset_to_equity = cls._number(balance.get("assetToEquity"))
        if asset_to_equity is not None and asset_to_equity > 0:
            return 1 - 1 / asset_to_equity
        return cls._number(balance.get("liabilityToAsset"))

    @staticmethod
    def _ts_code(code: str) -> str:
        exchange, symbol = code.split(".", 1)
        return f"{symbol}.{exchange.upper()}"

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fields = sorted({field for row in rows for field in row})
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
