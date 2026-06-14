"""Integration tests for NewsRepository.list_in_window — window selection on real SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.repositories.news_repository import NewsRepository


def _ts(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, 0, 0)


def _make(
    db: Session,
    *,
    title: str,
    fetched_at: datetime,
    published_at: datetime | None,
    url: str | None = None,
) -> NewsArticle:
    row = NewsArticle(
        fetched_at=fetched_at,
        source="gdelt:doc",
        title=title,
        description=None,
        url=url or f"https://example.test/{title}",
        published_at=published_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_returns_rows_with_published_at_inside_window(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    inside = _make(db, title="A", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 5, 14))
    before = _make(db, title="B", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 4, 23))
    after = _make(db, title="C", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 6, 1))

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=10)

    ids = {r.id for r in rows}
    assert inside.id in ids
    assert before.id not in ids
    assert after.id not in ids


def test_falls_back_to_fetched_at_when_published_at_is_null(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    matching = _make(db, title="A", fetched_at=_ts(2026, 6, 5, 12), published_at=None)
    not_matching = _make(db, title="B", fetched_at=_ts(2026, 6, 4, 12), published_at=None)

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=10)

    ids = {r.id for r in rows}
    assert matching.id in ids
    assert not_matching.id not in ids


def test_respects_limit(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    for i in range(5):
        _make(
            db,
            title=f"r{i}",
            fetched_at=_ts(2026, 6, 6, 3),
            published_at=_ts(2026, 6, 5, 10 + i),
        )

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=2)

    assert len(rows) == 2
