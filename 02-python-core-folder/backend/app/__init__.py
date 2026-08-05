from __future__ import annotations

from flask import Flask

from .api.v1.routes import api_v1
from .config import DevelopmentConfig
from .container import build_container
from .errors import register_error_handlers


def create_app(config_object: type[DevelopmentConfig] | None = None) -> Flask:
    """Create the HTTP shell without coupling model code to Flask."""
    app = Flask(__name__)
    app.config.from_object(config_object or DevelopmentConfig)
    app.extensions["container"] = build_container(app.config)

    app.register_blueprint(api_v1, url_prefix="/api/v1")
    register_error_handlers(app)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = app.config["CORS_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        return response

    return app
