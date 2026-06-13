from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Score, Summary


class ImportedSummary(Protocol):
    body: str
    created_at: datetime | None
    score: bool | None
    score_description: str | None

    @property
    def has_score(self) -> bool: ...


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

    def insert_imported_for_user(
        self,
        user_id: int,
        rows: Iterable[ImportedSummary],
    ) -> tuple[int, int]:
        summaries_inserted = 0
        scores_inserted = 0
        for row in rows:
            summary = Summary(
                user_id=user_id,
                summary=row.body,
                created_at=row.created_at,
            )
            self._session.add(summary)
            summaries_inserted += 1
            if row.has_score:
                self._session.flush()
                self._session.add(
                    Score(
                        summary_id=summary.id,
                        score=row.score,
                        description=row.score_description,
                    )
                )
                scores_inserted += 1
        return summaries_inserted, scores_inserted
