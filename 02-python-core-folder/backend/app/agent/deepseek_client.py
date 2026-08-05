from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from financial_risk.config import load_configs


class AgentUnavailableError(RuntimeError):
    pass


class DeepSeekAgentClient:
    """Small JSON-only DeepSeek client for the web-review agent."""

    def __init__(self, prompt_dir: str | Path):
        self.config = load_configs().ai
        self.prompt_dir = Path(prompt_dir)

    def prompt(self, name: str) -> str:
        return (self.prompt_dir / name).read_text(encoding="utf-8")

    def json_response(self, system_prompt: str, payload: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        api_key = os.getenv(self.config["api_key_env"])
        if not api_key:
            raise AgentUnavailableError(f"missing_environment_variable:{self.config['api_key_env']}")
        body = {
            "model": self.config["model"],
            "temperature": 0,
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        request = Request(
            self.config["base_url"].rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        max_retries = max(0, int(self.config.get("max_retries", 2)))
        initial_backoff = max(0.0, float(self.config.get("initial_backoff_seconds", 1)))
        max_backoff = max(initial_backoff, float(self.config.get("max_backoff_seconds", 8)))
        for attempt in range(max_retries + 1):
            retryable = True
            cause: Exception | None = None
            try:
                with urlopen(request, timeout=float(self.config.get("timeout_seconds", 75))) as response:
                    message = json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"]
                if not message:
                    raise AgentUnavailableError("empty_model_response")
                result = json.loads(message)
                if not isinstance(result, dict):
                    raise AgentUnavailableError("invalid_json_response")
                return result
            except HTTPError as error:
                cause = error
                retryable = error.code == 429 or error.code >= 500
                failure = AgentUnavailableError(f"deepseek_http_{error.code}")
            except (URLError, TimeoutError) as error:
                cause = error
                failure = AgentUnavailableError("deepseek_network_error")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
                cause = error
                failure = AgentUnavailableError("invalid_json_response")
            except AgentUnavailableError as error:
                cause = error
                failure = error
            if not retryable or attempt >= max_retries:
                raise failure from cause
            time.sleep(min(max_backoff, initial_backoff * (2 ** attempt)))
        raise AgentUnavailableError("deepseek_request_failed")
