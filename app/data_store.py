"""In-memory data store mimicking sensor feeds and incident lifecycle."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import itertools
import random
from typing import Any

SEVERITIES = ("low", "medium", "high", "critical")
STATUSES = ("open", "acknowledged", "resolved")
CATEGORIES = (
    "Traffic",
    "Cybersecurity",
    "Public Safety",
    "Utilities",
    "Environmental",
)

_rng = random.Random(42)
_incident_id_sequence = itertools.count(1001)

def _now() -> datetime:
    return datetime.now(UTC)


_incidents: list[dict[str, Any]] = [
    {
        "id": 1000,
        "title": "Traffic congestion at Central Station",
        "category": "Traffic",
        "severity": "high",
        "status": "open",
        "detected_at": _now() - timedelta(minutes=45),
        "acknowledged_at": None,
        "resolved_at": None,
        "location": "Central Station",
        "description": "Multiple sensors detect congestion exceeding 85% capacity.",
        "impact": "Delays to public transport lines 2, 3, and 5.",
        "root_cause": None,
    },
    {
        "id": 999,
        "title": "Unauthorized login attempts detected",
        "category": "Cybersecurity",
        "severity": "critical",
        "status": "acknowledged",
        "detected_at": _now() - timedelta(hours=2, minutes=15),
        "acknowledged_at": _now() - timedelta(hours=2),
        "resolved_at": None,
        "location": "Datacenter West",
        "description": "Spike of failed logins against admin APIs.",
        "impact": "Potential service disruption for citizen portal.",
        "root_cause": "Credential stuffing campaign",
    },
    {
        "id": 998,
        "title": "IoT air quality sensor offline",
        "category": "Environmental",
        "severity": "medium",
        "status": "resolved",
        "detected_at": _now() - timedelta(hours=6),
        "acknowledged_at": _now() - timedelta(hours=5, minutes=45),
        "resolved_at": _now() - timedelta(hours=5, minutes=10),
        "location": "Canal District",
        "description": "No data received for over 10 minutes.",
        "impact": "Air quality predictions may be delayed.",
        "root_cause": "Battery replacement required",
    },
]

_sensors: list[dict[str, Any]] = [
    {
        "id": "traffic-001",
        "type": "Traffic",
        "location": "Central Station",
        "last_update": _now() - timedelta(minutes=2),
        "status": "warning",
        "payload": {"vehicle_count": 982, "avg_speed_kmh": 8},
    },
    {
        "id": "iot-443",
        "type": "Utilities",
        "location": "Water Treatment Plant",
        "last_update": _now() - timedelta(minutes=6),
        "status": "healthy",
        "payload": {"chlorine_ppm": 1.1, "ph": 7.2},
    },
    {
        "id": "cctv-901",
        "type": "Public Safety",
        "location": "Museum Quarter",
        "last_update": _now() - timedelta(minutes=1),
        "status": "alert",
        "payload": {"anomaly_score": 0.81},
    },
]


def get_incidents() -> list[dict[str, Any]]:
    """Return a deep copy of incidents sorted by detection time."""
    return sorted((deepcopy(incident) for incident in _incidents), key=lambda item: item["detected_at"], reverse=True)


def get_incident(incident_id: int) -> dict[str, Any] | None:
    """Fetch a single incident by identifier."""
    for incident in _incidents:
        if incident["id"] == incident_id:
            return deepcopy(incident)
    return None


def add_incident(data: dict[str, Any]) -> dict[str, Any]:
    """Register a new incident from sensor analysis."""
    incident = {
        "id": next(_incident_id_sequence),
        "title": data.get("title", "Unclassified incident"),
        "category": data.get("category", _rng.choice(CATEGORIES)),
        "severity": data.get("severity", _rng.choice(SEVERITIES)),
        "status": "open",
        "detected_at": _now(),
        "acknowledged_at": None,
        "resolved_at": None,
        "location": data.get("location", "Unknown"),
        "description": data.get("description", "Generated from live sensor input."),
        "impact": data.get("impact", "Impact under investigation."),
        "root_cause": None,
    }
    _incidents.append(incident)
    return deepcopy(incident)


def update_incident_status(incident_id: int, status: str) -> dict[str, Any] | None:
    """Advance an incident through the response workflow."""
    if status not in STATUSES:
        raise ValueError(f"Unsupported incident status: {status}")

    for incident in _incidents:
        if incident["id"] == incident_id:
            incident["status"] = status
            now = _now()
            if status == "acknowledged" and incident["acknowledged_at"] is None:
                incident["acknowledged_at"] = now
            if status == "resolved":
                if incident["acknowledged_at"] is None:
                    incident["acknowledged_at"] = now
                incident["resolved_at"] = now
            return deepcopy(incident)
    return None


def get_sensors() -> list[dict[str, Any]]:
    """Return a copy of the simulated sensor status list."""
    return [deepcopy(sensor) for sensor in _sensors]


def mutate_sensor_payloads() -> None:
    """Mutate sensor payloads to mimic live telemetry."""
    for sensor in _sensors:
        jitter = _rng.uniform(-0.1, 0.1)
        sensor["last_update"] = _now()
        if sensor["type"] == "Traffic":
            payload = sensor["payload"]
            payload["vehicle_count"] = max(0, int(payload["vehicle_count"] * (1 + jitter)))
            payload["avg_speed_kmh"] = max(0, round(payload["avg_speed_kmh"] * (1 - jitter), 1))
            sensor["status"] = "alert" if payload["avg_speed_kmh"] < 10 else "warning"
        elif sensor["type"] == "Utilities":
            payload = sensor["payload"]
            payload["chlorine_ppm"] = round(max(0, payload["chlorine_ppm"] * (1 + jitter)), 2)
            payload["ph"] = round(min(8.5, max(6.5, payload["ph"] + jitter)), 2)
            sensor["status"] = "warning" if payload["chlorine_ppm"] > 1.5 else "healthy"
        elif sensor["type"] == "Public Safety":
            payload = sensor["payload"]
            payload["anomaly_score"] = round(min(1, max(0, payload["anomaly_score"] + jitter / 2)), 2)
            sensor["status"] = "alert" if payload["anomaly_score"] > 0.7 else "healthy"


def serialize_datetime(value: datetime | None) -> str | None:
    """Serialize datetimes consistently for JSON payloads."""
    return value.isoformat() if value else None


def serialize_incident(incident: dict[str, Any]) -> dict[str, Any]:
    """Prepare an incident dictionary for JSON responses."""
    record = deepcopy(incident)
    record["detected_at"] = serialize_datetime(record["detected_at"])
    record["acknowledged_at"] = serialize_datetime(record["acknowledged_at"])
    record["resolved_at"] = serialize_datetime(record["resolved_at"])
    return record


__all__ = [
    "SEVERITIES",
    "STATUSES",
    "CATEGORIES",
    "get_incidents",
    "get_incident",
    "add_incident",
    "update_incident_status",
    "get_sensors",
    "mutate_sensor_payloads",
    "serialize_incident",
]
