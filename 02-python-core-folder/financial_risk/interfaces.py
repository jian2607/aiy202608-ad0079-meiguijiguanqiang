"""模型内部模块间的正式协议与共享数据类型。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


Record = dict[str, Any]
Assessment = dict[str, Any]
PeerStats = dict[str, Any]
EMPTY_PEER_STATS: PeerStats = {"sample_count": 0, "percentile": None, "robust_z": None, "source": "none"}


@runtime_checkable
class ReferenceModel(Protocol):
    def describe(self, record: Record, metric: str, value: float) -> PeerStats: ...


@runtime_checkable
class ExplanationProvider(Protocol):
    def explain(self, assessment: Assessment) -> dict[str, Any]: ...
