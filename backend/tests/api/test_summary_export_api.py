"""API tests for GET /summary/export.csv."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Score, Summary, User


def test_export_requires_authentication(client: TestClient):
    resp = client.get("/summary/export.csv")
    assert resp.status_code == 401


def test_export_returns_header_only_when_user_has_no_summaries(authed_client: TestClient):
    resp = authed_client.get("/summary/export.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows == [["summary_id", "created_at_utc", "body", "score", "score_description"]]


def test_export_includes_summaries_newest_first(authed_client: TestClient, db: Session, user: User):
    db.add_all(
        [
            Summary(user_id=user.id, summary="oldest", created_at=datetime(2024, 1, 1)),
            Summary(user_id=user.id, summary="newest", created_at=datetime(2024, 12, 31)),
            Summary(user_id=user.id, summary="middle", created_at=datetime(2024, 6, 15)),
        ]
    )
    db.commit()

    resp = authed_client.get("/summary/export.csv")
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    bodies = [r[2] for r in rows[1:]]
    assert bodies == ["newest", "middle", "oldest"]


def test_export_includes_score_columns_when_user_rated(
    authed_client: TestClient, db: Session, user: User
):
    s = Summary(user_id=user.id, summary="rated", created_at=datetime(2024, 6, 1))
    db.add(s)
    db.commit()
    db.refresh(s)
    db.add(Score(summary_id=s.id, score=True, description="great"))
    db.commit()

    resp = authed_client.get("/summary/export.csv")
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    # One data row, with score columns populated.
    assert rows[1][3] == "TRUE"
    assert rows[1][4] == "great"


def test_export_excludes_other_users_summaries(authed_client: TestClient, db: Session, user: User):
    other = User(subject="other-user", email="other@example.com")
    db.add(other)
    db.commit()
    db.refresh(other)
    db.add(Summary(user_id=other.id, summary="not mine", created_at=datetime(2024, 6, 1)))
    db.add(Summary(user_id=user.id, summary="mine", created_at=datetime(2024, 6, 2)))
    db.commit()

    resp = authed_client.get("/summary/export.csv")
    rows = list(csv.reader(io.StringIO(resp.text)))
    bodies = [r[2] for r in rows[1:]]
    assert bodies == ["mine"]


def test_export_filename_is_dated(authed_client: TestClient):
    resp = authed_client.get("/summary/export.csv")
    cd = resp.headers["content-disposition"]
    assert 'filename="summaries-' in cd
    assert cd.endswith('.csv"')
