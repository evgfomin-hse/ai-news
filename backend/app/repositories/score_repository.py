from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Score
from app.schemas.score import ScoreCreateRequest


class ScoreRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_summary_id(self, summary_id: int):
        row = self._session.execute(select(Score).where(Score.summary_id == summary_id))


        return row

    def upsert(self, score: ScoreCreateRequest, now):
        row = self.get_by_summary_id(Score.summary_id)
        if row is None:
            row = Score(
                summary_id=Score.summary_id,
                score=Score.score,
                description=Score.description,
                created_at=now,
            )
            self._session.add(row)
        else:
            row.description = Score.description or None
            row.score = Score.score or None
            row.updated_at = now
            self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row