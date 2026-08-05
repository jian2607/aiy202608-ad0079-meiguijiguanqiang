from __future__ import annotations

from typing import Any

from ..curves import interpolate
from ..interfaces import EMPTY_PEER_STATS, Record, ReferenceModel
from ..utils import clamp
from .overrides import apply
from .scales import PeerScale


class MetricScorer:
    def __init__(self, rules: dict[str, Any], params: dict[str, Any], peer_scale: PeerScale):
        self.rules, self.params, self.peer_scale = rules, params, peer_scale

    def score(self, record: Record, metric: str, reference: ReferenceModel) -> dict[str, Any]:
        rule, value = self.rules[metric], record["metrics"].get(metric)
        special = apply(metric, record, value, self.params["metric_overrides"])
        if special is not None:
            absolute, status = special
        elif value is None:
            return {"label": rule["label"], "value": None, "score": None, "status": "unavailable", "absolute_score": None, "peer_score": None, "trend_score": None, "evidence": "关键字段缺失或指标不可计算"}
        else:
            absolute, status = interpolate(rule["anchors"], value), "available"
        peer = reference.describe(record, metric, value) if value is not None else dict(EMPTY_PEER_STATS)
        usable = self.peer_scale.is_usable(peer)
        peer_score = self.peer_scale.score(peer, rule["peer_direction"]) if usable else 0.0
        trend = float(record.get("trend_scores", {}).get(metric, 0.0))
        fusion = self.params["metric_fusion"]["with_peer" if usable else "without_peer"]
        score = fusion["absolute"] * absolute + fusion.get("peer", 0) * peer_score + fusion["trend"] * trend
        fragments = [f"{rule['label']}={value:.4g}" if value is not None else f"{rule['label']}=状态判定", f"绝对区间风险{absolute:.1f}"]
        if peer_score > 0: fragments.append(f"同行业异常风险{peer_score:.1f}")
        if trend > 0: fragments.append(f"历史恶化风险{trend:.1f}")
        return {"label": rule["label"], "value": value, "score": round(clamp(score, 0, 100), 2), "status": status, "absolute_score": round(absolute, 2), "peer_score": round(peer_score, 2), "trend_score": round(trend, 2), "peer": peer, "evidence": "；".join(fragments)}
