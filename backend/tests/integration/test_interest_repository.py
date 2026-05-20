from datetime import datetime

from sqlalchemy.orm import Session

from app.models import User
from app.repositories.interest_repository import InterestRepository


def test_get_latest_returns_none_when_no_rows(db: Session, user: User):
    assert InterestRepository(db).get_latest_for_user(user.id) is None


def test_upsert_inserts_new_row_when_missing(db: Session, user: User):
    repo = InterestRepository(db)
    now = datetime(2024, 1, 1)

    row = repo.upsert_interests(user.id, interests_text="ai", now=now)
    db.commit()

    assert row.id is not None
    assert row.interests == "ai"
    assert row.created_at == now
    assert row.updated_at == now


def test_upsert_updates_latest_row_in_place(db: Session, user: User):
    repo = InterestRepository(db)
    t0 = datetime(2024, 1, 1)
    t1 = datetime(2024, 2, 1)

    original = repo.upsert_interests(user.id, interests_text="ai", now=t0)
    db.commit()
    updated = repo.upsert_interests(user.id, interests_text="ml", now=t1)
    db.commit()

    assert updated.id == original.id
    assert updated.interests == "ml"
    assert updated.updated_at == t1


def test_upsert_normalizes_empty_string_to_none(db: Session, user: User):
    repo = InterestRepository(db)
    row = repo.upsert_interests(user.id, interests_text="", now=datetime(2024, 1, 1))
    db.commit()
    assert row.interests is None
