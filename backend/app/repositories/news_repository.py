from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import NewsArticle


class NewsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_many(self, articles: Iterable[NewsArticle]) -> int:
        rows = list(articles)
        if not rows:
            return 0
        self._session.add_all(rows)
        self._session.flush()
        return len(rows)

    def list_since(self, *, since: datetime, limit: int = 100) -> list[NewsArticle]:
        return list(
            self._session.scalars(
                select(NewsArticle)
                .where(NewsArticle.fetched_at >= since)
                .order_by(NewsArticle.fetched_at.desc(), NewsArticle.id.desc())
                .limit(limit)
            ).all()
        )

    def count_since(self, since: datetime) -> int:
        return int(
            self._session.scalar(
                select(func.count()).select_from(NewsArticle).where(NewsArticle.fetched_at >= since)
            )
            or 0
        )

    def list_in_window(self, *, start: datetime, end: datetime, limit: int) -> list[NewsArticle]:
        effective = func.coalesce(NewsArticle.published_at, NewsArticle.fetched_at)
        return list(
            self._session.scalars(
                select(NewsArticle)
                .where(and_(effective >= start, effective <= end))
                .order_by(NewsArticle.fetched_at.desc(), NewsArticle.id.desc())
                .limit(limit)
            ).all()
        )
