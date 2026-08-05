"""指标公式失效时的集中状态判定。"""

from __future__ import annotations

from typing import Any

from ..interfaces import Record


def apply(metric: str, record: Record, value: float | None, params: dict[str, Any]) -> tuple[float, str] | None:
    if metric == "ocf_net_profit_ratio" and value is None:
        net_profit, cashflow = record.get("net_profit"), record.get("operating_cashflow")
        if net_profit is None or cashflow is None or net_profit > 0:
            return None
        settings = params["cash_quality_state"]
        return (float(settings["loss_with_negative_cashflow"] if cashflow < 0 else settings["loss_with_positive_cashflow"]), settings["status"])
    if metric == "goodwill_equity_ratio" and record.get("equity") is not None and record["equity"] <= 0:
        settings = params["nonpositive_equity_goodwill"]
        return float(settings["score"]), settings["status"]
    return None
