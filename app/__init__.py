"""Application factory for the Smart City Incident Response demo."""
from __future__ import annotations

import os
from flask import Flask

from .routes import register_routes


def create_app(config: dict | None = None) -> Flask:
    """Application factory used by the WSGI entrypoint."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.update(
        SECRET_KEY=os.getenv("APP_SECRET", "dev-smart-city-secret"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=1800,
    )
    if config:
        app.config.update(config)

    register_routes(app)
    return app


__all__ = ["create_app"]
