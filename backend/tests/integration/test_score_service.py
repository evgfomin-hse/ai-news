from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models import Summary, User
from app.schemas.score import ScoreUpsertRequest
from app.services.score_service import ScoreService, SummaryNotFoundError


def _summary_for(db: Session, user: User) -> Summary:
    row = Summary(user_id=user.id, summary="body", created_at=datetime(2024, 1, 1))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_upsert_for_user_persists_score_and_commits(db: Session, user: User):
    summary = _summary_for(db, user)
    svc = ScoreService(db)

    row = svc.upsert_for_user(
        user.id,
        ScoreUpsertRequest(summary_id=summary.id, value=True, description="nice"),
    )

    # Use a fresh expire to prove the commit landed, not just a flush.
    db.expire_all()
    persisted = svc.get_by_summary_id(summary.id)
    assert persisted is not None
    assert persisted.id == row.id
    assert persisted.score is True
    assert persisted.description == "nice"


def test_upsert_for_user_rejects_unknown_summary(db: Session, user: User):
    svc = ScoreService(db)
    with pytest.raises(SummaryNotFoundError):
        svc.upsert_for_user(
            user.id,
            ScoreUpsertRequest(summary_id=12345, value=True, description=None),
        )


def test_upsert_for_user_rejects_other_users_summary(db: Session, user: User):
    other = User(google_id="other-sub", email="other@example.com", name="Other")
    db.add(other)
    db.commit()
    db.refresh(other)
    foreign = _summary_for(db, other)

    svc = ScoreService(db)
    with pytest.raises(SummaryNotFoundError):
        svc.upsert_for_user(
            user.id,
            ScoreUpsertRequest(summary_id=foreign.id, value=True, description=None),
        )


def test_upsert_for_user_is_idempotent(db: Session, user: User):
    summary = _summary_for(db, user)
    svc = ScoreService(db)

    first = svc.upsert_for_user(
        user.id, ScoreUpsertRequest(summary_id=summary.id, value=True, description="a")
    )
    second = svc.upsert_for_user(
        user.id, ScoreUpsertRequest(summary_id=summary.id, value=False, description="b")
    )

    assert first.id == second.id
    assert second.score is False
    assert second.description == "b"
