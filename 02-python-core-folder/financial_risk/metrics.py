"""财务指标计算。该模块只计算指标，不包含评分阈值。"""

from __future__ import annotations

from typing import Any

from .interfaces import Record
from .utils import safe_div


class MetricCalculator:
    def transform(self, records: list[Record]) -> list[Record]:
        ordered = sorted(records, key=lambda item: (str(item.get("ts_code", "")), str(item.get("report_period", "")), str(item.get("ann_date", ""))))
        prior: dict[tuple[str, str], dict[str, Any]] = {}
        enriched: list[Record] = []
        for record in ordered:
            key = (str(record.get("ts_code", "")), str(record.get("statement_type", "OTHER")))
            previous = prior.get(key)
            metrics, notes = self._calculate(record, previous)
            enriched.append({**record, "metrics": metrics, "calculation_notes": notes})
            prior[key] = record
        return enriched

    def _calculate(self, row: Record, previous: Record | None) -> tuple[dict[str, float | None], dict[str, str]]:
        assets = row.get("total_assets")
        liabilities = row.get("total_liabilities")
        equity = row.get("equity")
        current_assets = row.get("current_assets")
        current_liabilities = row.get("current_liabilities")
        inventory = row.get("inventory")
        revenue = row.get("revenue")
        operating_cost = row.get("operating_cost")
        net_profit = row.get("net_profit")
        deducted_net_profit = row.get("deducted_net_profit")
        operating_cashflow = row.get("operating_cashflow")
        ebit = row.get("ebit")
        interest = row.get("interest_expense")
        short_debt = (row.get("short_term_debt") or 0) + (row.get("current_portion_long_term_debt") or 0)
        notes: dict[str, str] = {}

        if interest is not None and interest <= 0:
            notes["interest_coverage"] = "利息支出非正，利息保障倍数不计算"
        if equity is not None and equity <= 0:
            notes["goodwill_equity_ratio"] = "净资产非正，商誉/净资产不按常规比率计算"
        if net_profit is not None and net_profit <= 0:
            notes["ocf_net_profit_ratio"] = "净利润非正，使用现金流状态规则"

        ar = row.get("accounts_receivable")
        prior_ar = previous.get("accounts_receivable") if previous else None
        average_ar = (ar + prior_ar) / 2 if ar is not None and prior_ar is not None else ar
        prior_inventory = previous.get("inventory") if previous else None
        average_inventory = (inventory + prior_inventory) / 2 if inventory is not None and prior_inventory is not None else inventory
        if previous is None:
            notes["receivable_days"] = "缺少上一期应收账款，使用期末余额近似"
            notes["inventory_days"] = "缺少上一期存货，使用期末余额近似"
            notes["revenue_growth"] = "缺少可比上一期营业收入，不计算营收增长率"

        metrics: dict[str, float | None] = {
            "debt_ratio": safe_div(liabilities, assets),
            "current_ratio": safe_div(current_assets, current_liabilities),
            "quick_ratio": safe_div((current_assets - inventory) if current_assets is not None and inventory is not None else None, current_liabilities),
            "interest_coverage": safe_div(ebit, interest) if interest is not None and interest > 0 else None,
            "cash_short_debt_ratio": safe_div(row.get("cash"), short_debt) if short_debt > 0 else None,
            "gross_margin": safe_div((revenue - operating_cost) if revenue is not None and operating_cost is not None else None, revenue),
            "net_margin": safe_div(net_profit, revenue),
            "deducted_net_profit_margin": safe_div(deducted_net_profit, revenue),
            "ocf_net_profit_ratio": safe_div(operating_cashflow, net_profit) if net_profit is not None and net_profit > 0 else None,
            "revenue_growth": safe_div(revenue - previous.get("revenue") if previous and revenue is not None and previous.get("revenue") is not None else None, abs(previous.get("revenue")) if previous and previous.get("revenue") is not None else None),
            "receivable_revenue_ratio": safe_div(ar, revenue),
            "receivable_days": safe_div(average_ar * 365 if average_ar is not None else None, revenue),
            "inventory_days": safe_div(average_inventory * 365 if average_inventory is not None else None, operating_cost),
            "goodwill_equity_ratio": safe_div(row.get("goodwill"), equity) if equity is not None and equity > 0 else None,
        }
        for metric in metrics:
            if row.get(metric) is not None:
                metrics[metric] = row[metric]
                notes[metric] = "使用数据源提供的标准化季度指标"
        return metrics, notes
