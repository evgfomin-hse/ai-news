"""OAuth login + e2e bootstrap — OAuth token verification is mocked."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture
def with_oauth_client_id(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-oauth-client-id")


def test_login_returns_503_when_client_id_missing(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    resp = client.post("/auth/login", json={"token": "x"})
    assert resp.status_code == 503


def test_login_returns_401_on_invalid_token(
    client: TestClient, monkeypatch, with_oauth_client_id
):
    from app.api import auth

    def _fail(*_a, **_k):
        raise ValueError("bad token")

    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", _fail)
    resp = client.post("/auth/login", json={"token": "bad"})
    assert resp.status_code == 401


def test_login_returns_401_when_payload_missing_sub(
    client: TestClient, monkeypatch, with_oauth_client_id
):
    from app.api import auth

    monkeypatch.setattr(
        auth.id_token, "verify_oauth2_token", lambda *_a, **_k: {"email": "a@b.com"}
    )
    resp = client.post("/auth/login", json={"token": "ok"})
    assert resp.status_code == 401


def test_login_creates_user_and_sets_session_cookie(
    client: TestClient, monkeypatch, with_oauth_client_id
):
    from app.api import auth

    monkeypatch.setattr(
        auth.id_token,
        "verify_oauth2_token",
        lambda *_a, **_k: {
            "sub": "oauth-sub-123",
            "email": "g@example.com",
            "name": "Goog User",
            "picture": "https://x/p.png",
        },
    )
    resp = client.post("/auth/login", json={"token": "ok"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "g@example.com"
    assert body["user"]["username"] == "Goog User"
    assert settings.session_cookie_name in resp.cookies


def test_e2e_bootstrap_session_requires_matching_secret(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "e2e_bootstrap_secret", "topsecret")
    bad = client.post("/auth/e2e/bootstrap-session", headers={"x-e2e-bootstrap-secret": "wrong"})
    assert bad.status_code == 401


def test_e2e_bootstrap_session_creates_user_with_secret(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "e2e_bootstrap_secret", "topsecret")
    resp = client.post(
        "/auth/e2e/bootstrap-session", headers={"x-e2e-bootstrap-secret": "topsecret"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "e2e-playwright@example.invalid"
    assert settings.session_cookie_name in resp.cookies
