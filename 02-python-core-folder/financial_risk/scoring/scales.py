from __future__ import annotations

from typing import Any

from ..curves import band_score, step_score


class PeerScale:
    def __init__(self, params: dict[str, Any]):
        self.minimum_sample_count = int(params["minimum_sample_count"])
        self.tail_bands = params["tail_bands"]
        self.robust_z_steps = params["robust_z_steps"]
        self.robust_z_top_score = float(params["robust_z_top_score"])

    def is_usable(self, peer: dict[str, Any]) -> bool:
        return peer["sample_count"] >= self.minimum_sample_count and peer["percentile"] is not None

    def score(self, peer: dict[str, Any], direction: str) -> float:
        if not self.is_usable(peer):
            return 0.0
        percentile = float(peer["percentile"])
        effective = percentile if direction == "high" else 1 - percentile
        return max(band_score(self.tail_bands, effective), step_score(self.robust_z_steps, abs(peer["robust_z"]) if peer["robust_z"] is not None else 0.0, self.robust_z_top_score))
