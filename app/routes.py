"""HTTP routes exposing the dashboard UI and JSON APIs."""
from __future__ import annotations

from functools import wraps
from typing import Any

from flask import (
    Blueprint,
    abort,
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
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if verify_credentials(username, password):
            session["user"] = {"username": username}
            target = request.args.get("next") or url_for("ui.dashboard")
            return redirect(target)
        error = "Invalid credentials"
        return render_template("login.html", error=error), 401
    if session.get("user"):
        return redirect(url_for("ui.dashboard"))
    return render_template("login.html")


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
    print("Help me")
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