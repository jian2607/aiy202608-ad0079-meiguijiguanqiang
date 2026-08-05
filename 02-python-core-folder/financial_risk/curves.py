"""无业务语义的数值映射原语；评分和趋势模块可共同复用。"""

from __future__ import annotations

from typing import Any


def interpolate(anchors: list[list[float]], value: float) -> float:
    points = sorted((float(x), float(y)) for x, y in anchors)
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:]):
        if left_x <= value <= right_x:
            ratio = (value - left_x) / (right_x - left_x) if right_x != left_x else 1.0
            return left_y + ratio * (right_y - left_y)
    return points[-1][1]


def band_score(bands: list[dict[str, float]], value: float) -> float:
    for band in bands:
        if value <= band["upper"]:
            return _within(band, value)
    return _within(bands[-1], value)


def _within(band: dict[str, float], value: float) -> float:
    span = band["upper"] - band["lower"]
    if span <= 0:
        return float(band["end"])
    ratio = (value - band["lower"]) / span
    return float(band["start"]) + ratio * (float(band["end"]) - float(band["start"]))


def step_score(steps: list[dict[str, float]], value: float, top_score: float) -> float:
    for step in steps:
        if value < step["below"]:
            return float(step["score"])
    return float(top_score)


def tier_value(tiers: list[dict[str, Any]], count: int, key: str) -> dict[str, Any] | None:
    for tier in sorted(tiers, key=lambda item: item[key], reverse=True):
        if count >= tier[key]:
            return tier
    return None
