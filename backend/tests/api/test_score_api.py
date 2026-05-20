from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Summary, User


def _add_summary(db: Session, owner_id: int) -> Summary:
    row = Summary(user_id=owner_id, summary="body", created_at=datetime(2024, 1, 1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_put_score_requires_authentication(client: TestClient):
    resp = client.put("/score", json={"summary_id": 1, "value": True})
    assert resp.status_code == 401


def test_put_score_inserts_row(authed_client: TestClient, db: Session, user: User):
    summary = _add_summary(db, user.id)

    resp = authed_client.put(
        "/score",
        json={"summary_id": summary.id, "value": True, "description": "great"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary_id"] == summary.id
    assert body["value"] is True
    assert body["description"] == "great"
    assert isinstance(body["id"], int)


def test_put_score_returns_404_for_unknown_summary(authed_client: TestClient):
    resp = authed_client.put(
        "/score",
        json={"summary_id": 9999, "value": True, "description": None},
    )
    assert resp.status_code == 404
    assert "Summary" in resp.json()["detail"]


def test_put_score_returns_404_for_other_users_summary(
    authed_client: TestClient, db: Session
):
    other = User(google_id="other", email="other@example.com")
    db.add(other)
    db.commit()
    db.refresh(other)
    foreign = _add_summary(db, other.id)

    resp = authed_client.put(
        "/score",
        json={"summary_id": foreign.id, "value": False, "description": None},
    )
    assert resp.status_code == 404


def test_put_score_validation_error_on_missing_field(authed_client: TestClient):
    resp = authed_client.put("/score", json={"summary_id": 1})
    assert resp.status_code == 422


def test_put_score_is_idempotent(authed_client: TestClient, db: Session, user: User):
    summary = _add_summary(db, user.id)

    first = authed_client.put(
        "/score",
        json={"summary_id": summary.id, "value": True, "description": "a"},
    ).json()
    second = authed_client.put(
        "/score",
        json={"summary_id": summary.id, "value": False, "description": "b"},
    ).json()

    assert first["id"] == second["id"]
    assert second["value"] is False
    assert second["description"] == "b"
