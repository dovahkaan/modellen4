"""HTTP routes exposing the dashboard UI and JSON APIs."""
from __future__ import annotations

import secrets
from functools import wraps
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import analytics
from .ai import build_incident_recommendation, classify_sensor_event
from .data_store import (
    SEVERITIES,
    add_incident,
    get_incident,
    get_incidents,
    get_sensors,
    mutate_sensor_payloads,
    serialize_incident,
    update_incident_status,
)
from .security import verify_credentials

ui_blueprint = Blueprint("ui", __name__)
api_blueprint = Blueprint("api", __name__, url_prefix="/api")
auth_blueprint = Blueprint("auth", __name__)


def login_required(view):
    """Ensure a user session exists before serving protected resources."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
                abort(401)
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    _remember_post_auth_target()
    github_context = {
        "github_client_id": current_app.config.get("GITHUB_CLIENT_ID"),
        "github_redirect_uri": current_app.config.get("GITHUB_REDIRECT_URI"),
        "github_state": _ensure_github_state(),
    }
    error_message = session.pop("auth_error", None)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if verify_credentials(username, password):
            session["user"] = {"username": username}
            target = _resolve_post_auth_target()
            return redirect(target)
        error_message = "Invalid credentials"
        return render_template("login.html", error=error_message, **github_context), 401
    if session.get("user"):
        return redirect(url_for("ui.dashboard"))
    return render_template("login.html", error=error_message, **github_context)


@auth_blueprint.route("/oauth/github/callback")
def github_callback():
    client_id = current_app.config.get("GITHUB_CLIENT_ID")
    client_secret = current_app.config.get("GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        session["auth_error"] = "GitHub login is not configured."
        return redirect(url_for("auth.login"))

    if request.args.get("error"):
        message = request.args.get("error_description") or "GitHub authorization was denied."
        session["auth_error"] = message
        return redirect(url_for("auth.login"))

    expected_state = session.get("github_oauth_state")
    received_state = request.args.get("state")
    if not expected_state or not received_state or received_state != expected_state:
        session["auth_error"] = "Invalid or expired GitHub login request. Please try again."
        session.pop("github_oauth_state", None)
        return redirect(url_for("auth.login"))
    session.pop("github_oauth_state", None)

    code = request.args.get("code")
    if not code:
        session["auth_error"] = "Missing authorization code from GitHub."
        return redirect(url_for("auth.login"))

    token_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": current_app.config.get("GITHUB_REDIRECT_URI"),
    }

    try:
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data=token_payload,
            timeout=10,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.exception("GitHub token exchange failed: %s", exc)
        session["auth_error"] = "Could not authenticate with GitHub. Please try again."
        return redirect(url_for("auth.login"))

    access_token = token_data.get("access_token")
    if not access_token:
        current_app.logger.error("GitHub token response missing access_token: %s", token_data)
        session["auth_error"] = "GitHub did not return an access token."
        return redirect(url_for("auth.login"))

    try:
        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        user_response.raise_for_status()
        user_data = user_response.json()
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.exception("GitHub user lookup failed: %s", exc)
        session["auth_error"] = "Unable to fetch GitHub profile information."
        return redirect(url_for("auth.login"))

    username = user_data.get("login")
    if not username:
        current_app.logger.error("GitHub profile response missing login: %s", user_data)
        session["auth_error"] = "GitHub profile is missing a username."
        return redirect(url_for("auth.login"))

    session["user"] = {
        "username": username,
        "name": user_data.get("name") or username,
        "avatar_url": user_data.get("avatar_url"),
        "auth_provider": "github",
    }

    target = _resolve_post_auth_target()
    return redirect(target)


@auth_blueprint.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.login"))


@ui_blueprint.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@api_blueprint.route("/incidents", methods=["GET", "POST"])
@login_required
def incidents_collection():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        incident = add_incident(payload)
        return jsonify({"incident": serialize_incident(incident)}), 201

    incidents = get_incidents()
    return jsonify({"incidents": [serialize_incident(item) for item in incidents]})


@api_blueprint.route("/incidents/<int:incident_id>", methods=["GET", "PATCH"])
@login_required
def incident_detail(incident_id: int):
    incident = get_incident(incident_id)
    if not incident:
        abort(404)

    if request.method == "PATCH":
        payload = request.get_json() or {}
        target_status = payload.get("status")
        if not target_status:
            abort(400, "Missing status property")
        updated = update_incident_status(incident_id, target_status)
        return jsonify({"incident": serialize_incident(updated)})

    return jsonify({"incident": serialize_incident(incident)})


@api_blueprint.route("/sensors")
@login_required
def sensors_collection():
    mutate_sensor_payloads()
    sensors = get_sensors()
    enriched = []
    for sensor in sensors:
        enriched.append({**sensor, "prediction": classify_sensor_event(sensor)})
    return jsonify({"sensors": _serialize_sensors(enriched)})


@api_blueprint.route("/dashboard")
@login_required
def dashboard_payload():
    incidents = get_incidents()
    metrics = analytics.calculate_metrics(incidents)
    sensors = get_sensors()
    sensors_with_predictions = []
    for sensor in sensors:
        sensors_with_predictions.append({**sensor, "prediction": classify_sensor_event(sensor)})
    return jsonify(
        {
            "incidents": [serialize_incident(item) for item in incidents],
            "metrics": metrics,
            "sensors": _serialize_sensors(sensors_with_predictions),
        }
    )


@api_blueprint.route("/simulate", methods=["POST"])
@login_required
def simulate_event():
    mutate_sensor_payloads()
    sensors = get_sensors()
    candidates = [classify_sensor_event(sensor) | {"sensor": sensor} for sensor in sensors]
    candidates.sort(key=lambda item: item["score"], reverse=True)
    top = candidates[0]
    created_incident: dict[str, Any] | None = None
    if top["score"] >= 0.5:
        payload = build_incident_recommendation(top["sensor"])
        created_incident = add_incident(payload)
    return jsonify(
        {
            "created_incident": serialize_incident(created_incident) if created_incident else None,
            "sensor_scores": [
                {
                    "sensor_id": item["sensor"]["id"],
                    "score": item["score"],
                    "suggested_severity": item["suggested_severity"],
                }
                for item in candidates
            ],
        }
    )


def _serialize_sensors(sensors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = []
    for sensor in sensors:
        copy = dict(sensor)
        timestamp = sensor.get("last_update")
        copy["last_update"] = timestamp.isoformat() if timestamp else None
        serialized.append(copy)
    return serialized


def register_routes(app):
    app.register_blueprint(ui_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(auth_blueprint)


def _ensure_github_state() -> str:
    state = session.get("github_oauth_state")
    if not state:
        state = secrets.token_urlsafe(16)
        session["github_oauth_state"] = state
    return state


def _resolve_post_auth_target() -> str:
    candidates = [session.pop("post_auth_redirect", None), request.args.get("next")]
    for candidate in candidates:
        if candidate and _is_safe_redirect(candidate):
            return candidate
    return url_for("ui.dashboard")


def _remember_post_auth_target() -> None:
    next_url = request.args.get("next")
    if next_url and _is_safe_redirect(next_url):
        session["post_auth_redirect"] = next_url


def _is_safe_redirect(target: str | None) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in {"http", "https"} and host_url.netloc == redirect_url.netloc