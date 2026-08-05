"""模型版本目录、配置快照和发布状态管理。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .config import CONFIG_FILES
from .utils import utc_now


class ModelRegistry:
    def initialize_candidate(self, model_dir: str | Path, config_dir: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
        root = Path(model_dir)
        root.mkdir(parents=True, exist_ok=True)
        snapshot = root / "config_snapshot"
        snapshot.mkdir(exist_ok=True)
        for filename in CONFIG_FILES.values():
            shutil.copy2(Path(config_dir) / filename, snapshot / filename)
        status = {"status": "candidate", "created_at": utc_now(), "updated_at": utc_now(), "training_manifest_sha256": manifest["input_sha256"], "as_of_date": manifest.get("metadata", {}).get("as_of_date")}
        self._write_status(root, status)
        return status

    def promote(self, model_dir: str | Path, status: str = "approved", note: str = "") -> dict[str, Any]:
        root = Path(model_dir)
        path = root / "release_status.json"
        if not (root / "industry_reference.json").exists():
            raise FileNotFoundError(f"未找到行业参考基准: {root / 'industry_reference.json'}")
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        current.update({"status": status, "updated_at": utc_now(), "note": note})
        self._write_status(root, current)
        return current

    @staticmethod
    def _write_status(root: Path, status: dict[str, Any]) -> None:
        (root / "release_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
