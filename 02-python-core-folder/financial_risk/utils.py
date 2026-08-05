"""不依赖第三方库的通用函数。"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--", "N/A", "nan", "None"}:
        return None
    try:
        value_float = float(text)
        return value_float if math.isfinite(value_float) else None
    except ValueError:
        return None


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def percentile_rank(sorted_values: list[float], value: float) -> float | None:
    if not sorted_values:
        return None
    less_or_equal = sum(item <= value for item in sorted_values)
    return less_or_equal / len(sorted_values)


def robust_z(value: float, values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    centre = median(values)
    mad = median([abs(item - centre) for item in values])
    if mad < 1e-12:
        return 0.0
    return (value - centre) / (1.4826 * mad)


def median_and_mad(values: Iterable[float]) -> tuple[float | None, float | None]:
    clean = list(values)
    if not clean:
        return None, None
    centre = median(clean)
    return centre, median([abs(item - centre) for item in clean])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
