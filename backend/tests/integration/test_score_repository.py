"""ScoreRepository against in-memory SQLite — covers insert + update paths of upsert."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Score, Summary, User
from app.repositories.score_repository import ScoreRepository
from app.schemas.score import ScoreUpsertRequest


@pytest.fixture
def summary(db: Session, user: User) -> Summary:
    row = Summary(user_id=user.id, summary="body", created_at=datetime(2024, 1, 1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_get_by_summary_id_returns_none_when_absent(db: Session):
    assert ScoreRepository(db).get_by_summary_id(999) is None


def test_upsert_inserts_new_row(db: Session, summary: Summary):
    repo = ScoreRepository(db)
    now = datetime(2024, 5, 1, 12, 0)
    req = ScoreUpsertRequest(summary_id=summary.id, value=True, description="great")

    row = repo.upsert(req, now=now)
    db.commit()

    assert isinstance(row, Score)
    assert row.id is not None
    assert row.summary_id == summary.id
    assert row.score is True
    assert row.description == "great"
    assert row.created_at == now
    assert row.updated_at == now


def test_upsert_updates_existing_row_without_changing_created_at(db: Session, summary: Summary):
    repo = ScoreRepository(db)
    t0 = datetime(2024, 5, 1, 12, 0)
    t1 = t0 + timedelta(hours=1)

    original = repo.upsert(
        ScoreUpsertRequest(summary_id=summary.id, value=True, description="ok"),
        now=t0,
    )
    db.commit()
    original_id = original.id

    updated = repo.upsert(
        ScoreUpsertRequest(summary_id=summary.id, value=False, description=None),
        now=t1,
    )
    db.commit()

    assert updated.id == original_id, "upsert must not create a duplicate row"
    assert updated.score is False
    assert updated.description is None
    assert updated.created_at == t0
    assert updated.updated_at == t1
