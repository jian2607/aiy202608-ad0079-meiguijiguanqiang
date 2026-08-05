"""读取项目根目录本地 .env 文件，不依赖第三方包。"""

from __future__ import annotations

import os
from pathlib import Path


def load_project_env() -> Path | None:
    """仅补充尚未设置的变量，系统环境变量始终优先。"""
    project_root = Path(__file__).resolve().parents[1]
    path = project_root / ".env"
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not value or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        os.environ[key] = value
    return path
