from fastapi.testclient import TestClient


def test_patch_profile_updates_fields(authed_client: TestClient):
    resp = authed_client.patch("/user", json={"name": "Renamed", "picture": "https://x/p.png"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "Renamed"
    assert body["avatarUrl"] == "https://x/p.png"

    # Round-trip via GET to prove it was persisted.
    assert authed_client.get("/user").json() == body


def test_patch_profile_noop_when_payload_empty(authed_client: TestClient):
    before = authed_client.get("/user").json()
    resp = authed_client.patch("/user", json={})
    assert resp.status_code == 200
    assert resp.json() == before


def test_patch_profile_requires_authentication(client: TestClient):
    assert client.patch("/user", json={"name": "x"}).status_code == 401
