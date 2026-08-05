from __future__ import annotations

from flask import jsonify


class AppError(Exception):
    status_code = 400
    code = "APPLICATION_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class DataQualityError(AppError):
    status_code = 422
    code = "DATA_QUALITY_REJECTED"


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(error):
        return jsonify({"success": False, "error": {"code": error.code, "message": error.message, "details": error.details}}), error.status_code

    @app.errorhandler(413)
    def handle_file_too_large(error):
        return jsonify({"success": False, "error": {"code": "FILE_TOO_LARGE", "message": "上传文件超过25MB限制", "details": {}}}), 413

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled application error")
        return jsonify({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "服务器处理失败", "details": {}}}), 500
