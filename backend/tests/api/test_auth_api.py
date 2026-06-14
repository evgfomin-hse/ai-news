from fastapi.testclient import TestClient


def test_logout_clears_session_cookie(client: TestClient):
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # FastAPI clears via Set-Cookie with empty value + Max-Age=0
    cookie_header = resp.headers.get("set-cookie", "")
    assert "session=" in cookie_header.lower()


def test_e2e_bootstrap_disabled_by_default(client: TestClient):
    resp = client.post("/auth/e2e/bootstrap-session")
    assert resp.status_code == 404


def test_user_profile_requires_authentication(client: TestClient):
    resp = client.get("/user")
    assert resp.status_code == 401


def test_user_profile_returns_current_user(authed_client: TestClient):
    resp = authed_client.get("/user")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "Test User"
    assert body["email"] == "test@example.com"
