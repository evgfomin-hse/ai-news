from fastapi.testclient import TestClient


def test_generate_requires_auth(client: TestClient):
    assert client.post("/summary/generate").status_code == 401


def test_generate_inserts_one_summary_row(authed_client: TestClient):
    resp = authed_client.post("/summary/generate")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "rows_inserted": 1}

    # Subsequent GET should see the row.
    listed = authed_client.get("/summary").json()
    assert listed["total"] == 1
    assert listed["items"][0]["body"].startswith("## Daily summary")


def test_generate_accepts_placeholder_flag(authed_client: TestClient):
    resp = authed_client.post("/summary/generate", json={"placeholder": True})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "rows_inserted": 1}

    listed = authed_client.get("/summary").json()
    assert listed["total"] == 1
    assert "Wire your own pipeline" in listed["items"][0]["body"]
