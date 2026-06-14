from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Score, Summary
from app.schemas.score import ScoreUpsertRequest


class ScoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_summary_id(self, summary_id: int) -> Score | None:
        return self._session.scalar(select(Score).where(Score.summary_id == summary_id))

    def list_recent_for_user(self, user_id: int, *, limit: int) -> list[Score]:
        return list(
            self._session.scalars(
                select(Score)
                .join(Summary, Summary.id == Score.summary_id)
                .where(Summary.user_id == user_id)
                .order_by(Score.updated_at.desc().nulls_last(), Score.id.desc())
                .limit(limit)
            ).all()
        )

    def upsert(self, request: ScoreUpsertRequest, *, now: datetime) -> Score:
        row = self.get_by_summary_id(request.summary_id)
        if row is None:
            row = Score(
                summary_id=request.summary_id,
                score=request.value,
                description=request.description,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.score = request.value
            row.description = request.description
            row.updated_at = now
        self._session.flush()
        self._session.refresh(row)
        return row
