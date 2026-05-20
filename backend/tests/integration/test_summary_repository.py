from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Summary, User
from app.repositories.summary_repository import SummaryRepository


def _add_summary(db: Session, user: User, n: int) -> list[Summary]:
    rows = [
        Summary(user_id=user.id, summary=f"s{i}", created_at=datetime(2024, 1, i + 1))
        for i in range(n)
    ]
    db.add_all(rows)
    db.commit()
    return rows


def test_count_for_user_returns_zero_when_empty(db: Session, user: User):
    assert SummaryRepository(db).count_for_user(user.id) == 0


def test_count_for_user_only_counts_owned_rows(db: Session, user: User):
    other = User(google_id="x", email="x@example.com")
    db.add(other)
    db.commit()
    db.refresh(other)
    _add_summary(db, user, 3)
    _add_summary(db, other, 5)

    assert SummaryRepository(db).count_for_user(user.id) == 3


def test_list_page_returns_rows_in_created_at_desc(db: Session, user: User):
    _add_summary(db, user, 5)
    repo = SummaryRepository(db)
    page = repo.list_page_for_user(user.id, offset=0, limit=3)
    assert [r.summary for r in page] == ["s4", "s3", "s2"]


def test_list_page_respects_offset_and_limit(db: Session, user: User):
    _add_summary(db, user, 5)
    repo = SummaryRepository(db)
    page = repo.list_page_for_user(user.id, offset=2, limit=2)
    assert [r.summary for r in page] == ["s2", "s1"]


def test_exists_for_user_is_true_only_for_owner(db: Session, user: User):
    [first, *_] = _add_summary(db, user, 1)
    other = User(google_id="x2", email="x2@example.com")
    db.add(other)
    db.commit()

    repo = SummaryRepository(db)
    assert repo.exists_for_user(first.id, user_id=user.id) is True
    assert repo.exists_for_user(first.id, user_id=other.id) is False
    assert repo.exists_for_user(99999, user_id=user.id) is False
