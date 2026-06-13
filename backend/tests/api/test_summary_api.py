from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Score, Summary, User


def test_empty_state_returns_notice_and_zero_total(authed_client: TestClient):
    resp = authed_client.get("/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["total_pages"] == 0
    assert body["items"] == []
    assert "No summaries yet" in body["notice"]


def test_paginates_results(authed_client: TestClient, db: Session, user: User):
    db.add_all(
        Summary(user_id=user.id, summary=f"s{i}", created_at=datetime(2024, 1, i + 1))
        for i in range(5)
    )
    db.commit()

    resp = authed_client.get("/summary", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert body["total_pages"] == 3
    assert len(body["items"]) == 2


def test_rejects_invalid_pagination(authed_client: TestClient):
    assert authed_client.get("/summary", params={"page": 0}).status_code == 422
    assert authed_client.get("/summary", params={"page_size": 101}).status_code == 422


def test_requires_authentication(client: TestClient):
    assert client.get("/summary").status_code == 401


def test_delete_removes_summary_and_associated_score(
    authed_client: TestClient, db: Session, user: User
):
    summary = Summary(user_id=user.id, summary="delete me")
    db.add(summary)
    db.commit()
    db.refresh(summary)

    score = Score(summary_id=summary.id, score=True, description="good")
    db.add(score)
    db.commit()

    resp = authed_client.delete(f"/summary/{summary.id}")
    assert resp.status_code == 204

    assert db.query(Summary).filter(Summary.id == summary.id).count() == 0
    assert db.query(Score).filter(Score.summary_id == summary.id).count() == 0
