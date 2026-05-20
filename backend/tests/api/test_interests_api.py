from fastapi.testclient import TestClient


def test_get_returns_empty_state_when_user_has_none(authed_client: TestClient):
    resp = authed_client.get("/interests")
    assert resp.status_code == 200
    assert resp.json() == {"interestId": None, "interests": ""}


def test_patch_persists_and_round_trips(authed_client: TestClient):
    patch = authed_client.patch("/interests", json={"interests": "  ai  "})
    assert patch.status_code == 200
    body = patch.json()
    assert body["interests"] == "ai"  # trimmed
    assert isinstance(body["interestId"], int)

    get = authed_client.get("/interests").json()
    assert get == body


def test_patch_rejects_excessively_long_payload(authed_client: TestClient):
    resp = authed_client.patch("/interests", json={"interests": "x" * 50_001})
    assert resp.status_code == 422
