from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from ..errors import DataQualityError, ValidationError


class ImportReportService:
    def __init__(self, repository, risk_engine, upload_dir: str):
        self.repository = repository
        self.risk_engine = risk_engine
        self.upload_dir = Path(upload_dir)

    def execute(self, uploaded_file):
        if not uploaded_file or not uploaded_file.filename:
            raise ValidationError("请选择CSV季度财报文件")
        filename = secure_filename(uploaded_file.filename)
        if not filename.lower().endswith(".csv"):
            raise ValidationError("当前版本只支持CSV格式；Parquet可在后续数据适配器中启用")

        destination = self.upload_dir / str(uuid4()) / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        uploaded_file.save(destination)
        prepared = self.risk_engine.prepare_csv(str(destination))
        summary = prepared["quality_summary"]
        if summary.get("errors", 0):
            raise DataQualityError("上传文件未通过数据质量检查", {"quality_summary": summary, "issues": prepared["issues"][:20]})

        accepted = [record for record in prepared["records"] if record.get("statement_type") in {"Q1", "H1", "Q3"}]
        rejected_count = len(prepared["records"]) - len(accepted)
        if not accepted:
            raise DataQualityError("文件中没有可用的Q1、H1或Q3季度报告", {"quality_summary": summary})

        manifest = {"source": "user_upload", "file_name": filename, "accepted_count": len(accepted), "rejected_non_quarter_count": rejected_count}
        stored = self.repository.upsert_reports(accepted, "user_upload", manifest)
        return {"file_name": filename, "quality_summary": summary, "accepted_count": len(accepted), "rejected_non_quarter_count": rejected_count, "storage": stored}
