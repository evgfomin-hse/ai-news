"""API tests for POST /summary/import.csv."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Score, Summary, User
from app.services.summary_export import CSV_HEADER

HEADER_LINE = ",".join(CSV_HEADER)


def _upload(client: TestClient, csv_text: str):
    return client.post(
        "/summary/import.csv",
        files={"file": ("summaries.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    )


def test_import_requires_authentication(client: TestClient):
    resp = _upload(client, f"{HEADER_LINE}\n1,,body,,\n")
    assert resp.status_code == 401


def test_import_creates_summaries_and_scores(
    authed_client: TestClient, db: Session, user: User
):
    csv_text = (
        f"{HEADER_LINE}\n"
        "5,2024-01-01T00:00:00,first,,\n"
        "6,2024-06-02T00:00:00,second,TRUE,great\n"
    )
    resp = _upload(authed_client, csv_text)
    assert resp.status_code == 200
    assert resp.json() == {"summaries_imported": 2, "scores_imported": 1}

    summaries = db.query(Summary).filter(Summary.user_id == user.id).all()
    assert {s.summary for s in summaries} == {"first", "second"}
    score = db.query(Score).one()
    assert score.score is True
    assert score.description == "great"


def test_import_ignores_summary_id_and_creates_new_rows(
    authed_client: TestClient, db: Session, user: User
):
    # A pre-existing row whose id collides with the CSV's summary_id column.
    existing = Summary(user_id=user.id, summary="existing")
    db.add(existing)
    db.commit()
    db.refresh(existing)

    resp = _upload(authed_client, f"{HEADER_LINE}\n{existing.id},,imported,,\n")
    assert resp.status_code == 200
    assert resp.json()["summaries_imported"] == 1

    # The existing row is untouched and a brand-new row was added.
    bodies = [s.summary for s in db.query(Summary).filter(Summary.user_id == user.id).all()]
    assert sorted(bodies) == ["existing", "imported"]


def test_import_assigns_rows_to_current_user(
    authed_client: TestClient, db: Session, user: User
):
    _upload(authed_client, f"{HEADER_LINE}\n1,,mine,,\n")
    row = db.query(Summary).filter(Summary.summary == "mine").one()
    assert row.user_id == user.id


def test_invalid_csv_returns_400_and_imports_nothing(
    authed_client: TestClient, db: Session, user: User
):
    csv_text = (
        f"{HEADER_LINE}\n"
        "1,,good,,\n"
        "2,,bad,MAYBE,\n"  # invalid score → whole import rejected
    )
    resp = _upload(authed_client, csv_text)
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "invalid_csv"
    assert any("MAYBE" in p for p in detail["problems"])
    # All-or-nothing: the valid row was not written either.
    assert db.query(Summary).filter(Summary.user_id == user.id).count() == 0


def test_bad_header_returns_400(authed_client: TestClient):
    resp = _upload(authed_client, "a,b,c\n1,2,3\n")
    assert resp.status_code == 400
    assert "Unexpected header" in resp.json()["detail"]["problems"][0]


def test_export_then_import_round_trips(
    authed_client: TestClient, db: Session, user: User
):
    s = Summary(user_id=user.id, summary="round trip me")
    db.add(s)
    db.commit()
    db.refresh(s)
    db.add(Score(summary_id=s.id, score=False, description="meh"))
    db.commit()

    exported = authed_client.get("/summary/export.csv").text
    resp = authed_client.post(
        "/summary/import.csv",
        files={"file": ("e.csv", io.BytesIO(exported.encode("utf-8")), "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"summaries_imported": 1, "scores_imported": 1}
    # Original + imported copy.
    assert db.query(Summary).filter(Summary.user_id == user.id).count() == 2
