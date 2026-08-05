from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_project_env() -> None:
    """Load local development secrets without overriding real process variables."""
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name:
            os.environ.setdefault(name, value)


load_project_env()


class DevelopmentConfig:
    TESTING = False
    CORS_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    DATABASE_PATH = str(PROJECT_ROOT / "data" / "financial_risk.sqlite")
    MODEL_DIR = str(PROJECT_ROOT / "artifacts")
    UPLOAD_DIR = str(PROJECT_ROOT / "data" / "users" / "local" / "uploads")
    AI_CACHE_DIR = str(PROJECT_ROOT / "artifacts" / "ai_cache")
    AGENT_PROMPT_DIR = str(PROJECT_ROOT / "backend" / "prompts" / "company_web_review")
    AGENT_SEARCH_TIMEOUT_SECONDS = float(os.getenv("AGENT_SEARCH_TIMEOUT_SECONDS", "20"))
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
