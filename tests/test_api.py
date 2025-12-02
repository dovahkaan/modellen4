from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app():
    return create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "GITHUB_CLIENT_ID": "test-client",
            "GITHUB_CLIENT_SECRET": "test-secret",
            "SERVER_NAME": "localhost",
        }
    )


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


def test_github_oauth_success(client, monkeypatch):
    client.get("/login?next=/api/dashboard")

    with client.session_transaction() as session_obj:
        state = session_obj["github_oauth_state"]

    captured_token_payload = {}

    def fake_post(url, headers=None, data=None, timeout=None):
        captured_token_payload["url"] = url
        captured_token_payload["data"] = data

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "token123"}

        return FakeResponse()

    def fake_get(url, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer token123"

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"login": "octocat", "name": "Octo Cat", "avatar_url": "https://example.com/avatar"}

        return FakeResponse()

    monkeypatch.setattr("app.routes.requests.post", fake_post)
    monkeypatch.setattr("app.routes.requests.get", fake_get)

    response = client.get(f"/oauth/github/callback?code=abc123&state={state}")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/api/dashboard")

    with client.session_transaction() as session_obj:
        assert session_obj["user"]["username"] == "octocat"
        assert "github_oauth_state" not in session_obj

    assert captured_token_payload["url"].endswith("/access_token")
    assert captured_token_payload["data"]["code"] == "abc123"


def test_github_oauth_invalid_state(client):
    client.get("/login")

    response = client.get("/oauth/github/callback?code=ignored&state=invalid-state")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction() as session_obj:
        assert session_obj["auth_error"].startswith("Invalid or expired GitHub login request")
