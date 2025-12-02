from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})


@pytest.fixture()
def client(app):
    with app.test_client() as client:
        yield client


def login(client):
    return client.post(
        "/login",
        data={"username": "incident-operator", "password": "secure-demo"},
        follow_redirects=False,
    )


def test_login_required(client):
    response = client.get("/api/dashboard", headers={"Accept": "application/json"})
    assert response.status_code == 401


def test_successful_login(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_incident_lifecycle(client):
    login(client)
    listing = client.get("/api/incidents")
    assert listing.status_code == 200
    initial_count = len(listing.get_json()["incidents"])

    created = client.post(
        "/api/incidents",
        json={"title": "Test incident", "category": "Utilities", "severity": "medium"},
    )
    assert created.status_code == 201
    incident_id = created.get_json()["incident"]["id"]

    updated = client.patch(f"/api/incidents/{incident_id}", json={"status": "resolved"})
    assert updated.status_code == 200
    assert updated.get_json()["incident"]["status"] == "resolved"

    refreshed = client.get("/api/incidents")
    assert len(refreshed.get_json()["incidents"]) == initial_count + 1
