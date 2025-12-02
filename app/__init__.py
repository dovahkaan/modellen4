"""Application factory for the Smart City Incident Response demo."""
from __future__ import annotations

import os
from flask import Flask

from .routes import register_routes


def create_app(config: dict | None = None) -> Flask:
    """Application factory used by the WSGI entrypoint."""
    github_client_id = os.getenv("GITHUB_CLIENT_ID")
    if github_client_id:
        github_client_id = github_client_id.strip()

    github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    if github_client_secret:
        github_client_secret = github_client_secret.strip()

    github_redirect_uri = os.getenv(
        "GITHUB_REDIRECT_URI", "http://127.0.0.1:5000/oauth/github/callback"
    )
    if github_redirect_uri:
        github_redirect_uri = github_redirect_uri.strip()

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
        GITHUB_CLIENT_ID=github_client_id,
        GITHUB_REDIRECT_URI=github_redirect_uri,
        GITHUB_CLIENT_SECRET=github_client_secret,
    )
    if config:
        app.config.update(config)

    register_routes(app)
    return app


__all__ = ["create_app"]
