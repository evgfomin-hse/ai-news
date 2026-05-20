from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.models import Score
from app.repositories.score_repository import ScoreRepository
from app.repositories.summary_repository import SummaryRepository
from app.schemas.score import ScoreUpsertRequest


class SummaryNotFoundError(LookupError):
    """Raised when a score targets a summary that does not exist for the user."""


class ScoreService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._scores = ScoreRepository(session)
        self._summaries = SummaryRepository(session)

    def get_by_summary_id(self, summary_id: int) -> Score | None:
        return self._scores.get_by_summary_id(summary_id)

    def upsert_for_user(self, user_id: int, request: ScoreUpsertRequest) -> Score:
        if not self._summaries.exists_for_user(request.summary_id, user_id=user_id):
            raise SummaryNotFoundError(request.summary_id)
        row = self._scores.upsert(request, now=naive_utc_now())
        self._session.commit()
        self._session.refresh(row)
        return row
