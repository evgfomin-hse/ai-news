from fastapi.testclient import TestClient

from app.core.config import settings


def test_disabled_when_secret_not_configured(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "summary_job_secret", "")
    resp = client.post("/tasks/summary/run-bulk")
    assert resp.status_code == 404


def test_rejects_wrong_secret(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "summary_job_secret", "right")
    resp = client.post(
        "/tasks/summary/run-bulk", headers={"x-summary-job-secret": "wrong"}
    )
    assert resp.status_code == 401


def test_runs_with_correct_secret(client: TestClient, monkeypatch, db, user):
    monkeypatch.setattr(settings, "summary_job_secret", "right")
    resp = client.post(
        "/tasks/summary/run-bulk", headers={"x-summary-job-secret": "right"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["users"] == 1
    assert body["rows_inserted"] == 1
