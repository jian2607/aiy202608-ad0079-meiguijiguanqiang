from __future__ import annotations

from flask import jsonify


def success(data, status_code: int = 200):
    return jsonify({"success": True, "data": data}), status_code
