from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Score, Summary


class SummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists_for_user(self, summary_id: int, *, user_id: int) -> bool:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(Summary)
                .where(Summary.id == summary_id, Summary.user_id == user_id)
            )
            > 0
        )

    def list_all_with_scores_for_user(self, user_id: int) -> list[tuple[Summary, Score | None]]:
        """Every summary for `user_id`, newest first, left-joined to its score (if any).

        Used by the CSV export path. No pagination — the export endpoint is rare and
        single-user, and the coursework dataset is small.
        """
        rows = self._session.execute(
            select(Summary, Score)
            .outerjoin(Score, Score.summary_id == Summary.id)
            .where(Summary.user_id == user_id)
            .order_by(Summary.created_at.desc().nulls_last(), Summary.id.desc())
        ).all()
        return [(row[0], row[1]) for row in rows]

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

    def delete_for_user(self, summary_id: int, *, user_id: int) -> bool:
        """Delete a summary owned by user_id. Returns True if a row was deleted."""
        row = self._session.scalar(
            select(Summary).where(Summary.id == summary_id, Summary.user_id == user_id)
        )
        if row is None:
            return False
        self._session.delete(row)
        return True

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
