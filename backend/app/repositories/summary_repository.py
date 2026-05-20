from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Summary


class SummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists_for_user(self, summary_id: int, *, user_id: int) -> bool:
        return self._session.scalar(
            select(func.count())
            .select_from(Summary)
            .where(Summary.id == summary_id, Summary.user_id == user_id)
        ) > 0

    def count_for_user(self, user_id: int) -> int:
        return int(
            self._session.scalar(
                select(func.count()).select_from(Summary).where(Summary.user_id == user_id)
            )
            or 0
        )

    def list_page_for_user(
        self,
        user_id: int,
        *,
        offset: int,
        limit: int,
    ) -> list[Summary]:
        return list(
            self._session.scalars(
                select(Summary)
                .where(Summary.user_id == user_id)
                .order_by(Summary.created_at.desc().nulls_last(), Summary.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )

    def append_row(
        self,
        *,
        user_id: int,
        summary: str,
        created_at: datetime,
    ) -> None:
        self._session.add(
            Summary(
                user_id=user_id,
                summary=summary,
                created_at=created_at,
            )
        )
