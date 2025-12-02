
"""Analytics helpers to keep route handlers lean."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from .data_store import STATUSES


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    if not start or not end:
        return None
    return (end - start).total_seconds() / 60


def calculate_metrics(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics for the dashboard cards and charts."""
    totals = Counter(incident["status"] for incident in incidents)
    by_category = Counter(incident["category"] for incident in incidents)
    by_severity = Counter(incident["severity"] for incident in incidents)

    acknowledgement_times = [
        _minutes_between(incident["detected_at"], incident["acknowledged_at"])
        for incident in incidents
        if incident["acknowledged_at"]
    ]
    resolution_times = [
        _minutes_between(incident["acknowledged_at"] or incident["detected_at"], incident["resolved_at"])
        for incident in incidents
        if incident["resolved_at"]
    ]

    timeline = defaultdict(int)
    for incident in incidents:
        key = incident["detected_at"].strftime("%Y-%m-%d %H:00")
        timeline[key] += 1

    return {
        "total_incidents": len(incidents),
        "status_breakdown": {status: totals.get(status, 0) for status in STATUSES},
        "category_breakdown": dict(by_category),
        "severity_breakdown": dict(by_severity),
        "avg_ack_minutes": round(sum(acknowledgement_times) / len(acknowledgement_times), 1)
        if acknowledgement_times
        else None,
        "avg_resolution_minutes": round(sum(resolution_times) / len(resolution_times), 1)
        if resolution_times
        else None,
        "incidents_timeline": sorted(timeline.items(), key=lambda item: item[0]),
    }
