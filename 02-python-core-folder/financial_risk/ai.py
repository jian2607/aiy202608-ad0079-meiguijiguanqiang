"""可替换的AI说明层。AI绝不参与正式风险分计算。"""

from __future__ import annotations

import json
import os
import random
import socket
import time
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .interfaces import Assessment, ExplanationProvider


class NullProvider:
    def __init__(self, reason: str = "未启用AI"):
        self.reason = reason

    def explain(self, assessment: Assessment) -> dict[str, Any]:
        return {"status": "disabled", "reason": self.reason, "findings": []}


class DeepSeekFlashProvider:
    def __init__(self, config: dict[str, Any], cache_dir: str | Path | None = None):
        self.config = config
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.last_call_at = 0.0
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def explain(self, assessment: Assessment) -> dict[str, Any]:
        api_key = os.getenv(self.config["api_key_env"])
        if not api_key:
            return {"status": "skipped", "reason": f"未设置环境变量 {self.config['api_key_env']}", "findings": []}
        facts = self._facts(assessment)
        key = self._cache_key(facts)
        cached = self._read_cache(key)
        if cached:
            return {**cached, "cache_hit": True, "cache_key": key}
        body = self._body(facts)
        started, last_error = time.monotonic(), None
        attempts = int(self.config.get("max_retries", 3)) + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self._request(body, api_key)
                result = {"status": "ok", "provider": "deepseek", "model": self.config["model"], "result": self._validate(json.loads(response["choices"][0]["message"]["content"]), facts), "retry_count": attempt - 1, "latency_ms": round((time.monotonic() - started) * 1000), "cache_hit": False, "cache_key": key}
                self._write_cache(key, result)
                return result
            except Exception as error:
                last_error = error
                if attempt == attempts or not self._retryable(error):
                    break
                self._backoff(attempt)
        return {"status": "failed", "reason": self._error_reason(last_error), "retry_count": attempts - 1, "latency_ms": round((time.monotonic() - started) * 1000), "cache_hit": False, "cache_key": key, "core_risk_score_available": True, "requires_ai_retry": self._retryable(last_error), "findings": []}

    def _request(self, body: dict[str, Any], api_key: str) -> dict[str, Any]:
        delay = float(self.config.get("request_interval_seconds", 0)) - (time.monotonic() - self.last_call_at)
        if delay > 0:
            time.sleep(delay)
        request = Request(self.config["base_url"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
        self.last_call_at = time.monotonic()
        with urlopen(request, timeout=float(self.config.get("timeout_seconds", 75))) as response:
            return json.loads(response.read().decode("utf-8"))

    def _body(self, facts: dict[str, Any]) -> dict[str, Any]:
        return {"model": self.config["model"], "temperature": self.config.get("temperature", 0), "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "你是财务风险报告助手。只能引用用户提供的结构化事实，不能预测未来，也不能编造数值、法规、公司事件或原文。返回JSON对象：summary_items、risk_tags、review_items。每个对象均必须包含evidence字段，且evidence必须逐字等于输入中的一条证据；没有证据时不要输出该对象。"}, {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}]}

    def _facts(self, assessment: Assessment) -> dict[str, Any]:
        threshold = float(self.config.get("evidence_score_threshold", 40))
        metrics = [{"metric": name, "label": detail["label"], "value": detail["value"], "risk_score": detail["score"], "evidence": detail["evidence"]} for name, detail in assessment["metrics"].items() if detail["score"] is not None and detail["score"] >= threshold]
        return {"instruction": "仅根据以下事实生成风险说明，不做未来预测。", "company": assessment.get("ts_code"), "report_period": assessment.get("report_period"), "risk_score": assessment.get("risk_score"), "risk_level": assessment.get("risk_level"), "risk_floor_reasons": assessment["risk_floor"]["reasons"], "synergy": assessment["synergy"], "metrics": metrics}

    @staticmethod
    def _validate(result: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
        allowed = {item["evidence"] for item in facts["metrics"]} | set(facts.get("risk_floor_reasons", []))
        summaries = [str(item.get("text", "")) for item in result.get("summary_items", []) if isinstance(item, dict) and item.get("evidence") in allowed and str(item.get("text", "")).strip()]
        tags = [{"name": str(item.get("name", "未命名标签")), "evidence": item["evidence"], "confidence": item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None} for item in result.get("risk_tags", []) if isinstance(item, dict) and item.get("evidence") in allowed]
        review_items = [str(item.get("item", "")) for item in result.get("review_items", []) if isinstance(item, dict) and item.get("evidence") in allowed and str(item.get("item", "")).strip()]
        return {"summary": "；".join(summaries), "risk_tags": tags, "review_items": review_items}

    def _cache_key(self, facts: dict[str, Any]) -> str:
        stable = json.dumps({"facts": facts, "model": self.config["model"], "prompt_version": self.config.get("prompt_version", "1")}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(stable.encode("utf-8")).hexdigest()

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if not path or not path.exists(): return None
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            return cached if cached.get("status") == "ok" else None
        except json.JSONDecodeError:
            return None

    def _write_cache(self, key: str, result: dict[str, Any]) -> None:
        if self.cache_dir and result.get("status") == "ok":
            (self.cache_dir / f"{key}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    def _backoff(self, attempt: int) -> None:
        seconds = min(float(self.config.get("max_backoff_seconds", 12)), float(self.config.get("initial_backoff_seconds", 2)) * 2 ** (attempt - 1))
        time.sleep(seconds + random.uniform(0, min(0.5, seconds * 0.1)))

    @staticmethod
    def _retryable(error: Exception | None) -> bool:
        if error is None: return False
        if isinstance(error, HTTPError): return error.code in {408, 429} or 500 <= error.code < 600
        return isinstance(error, (URLError, TimeoutError, socket.timeout, ConnectionError))

    @staticmethod
    def _error_reason(error: Exception | None) -> str:
        if isinstance(error, HTTPError): return f"HTTP {error.code}"
        if isinstance(error, (TimeoutError, socket.timeout)): return "request_timeout"
        if isinstance(error, URLError): return "network_error"
        if isinstance(error, json.JSONDecodeError): return "invalid_json_response"
        return type(error).__name__ if error else "unknown_error"


PROVIDERS = {"deepseek": DeepSeekFlashProvider}


def build_provider(config: dict[str, Any], enabled: bool, cache_dir: str | Path | None = None) -> ExplanationProvider:
    if not enabled:
        return NullProvider()
    provider = PROVIDERS.get(config.get("provider", ""))
    return provider(config, cache_dir) if provider else NullProvider(f"未知的AI提供方: {config.get('provider') or '未配置'}")
