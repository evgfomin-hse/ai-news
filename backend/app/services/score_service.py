from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.models import User
from app.models.score import Score
from app.repositories.score_repository import ScoreRepository
from app.repositories.user_repository import UserRepository
from app.schemas.score import ScoreCreateRequest


class ScoreService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._score = ScoreRepository(session)

    def get_by_summary_id(self, summary_id: int) -> Score:
        return self._score.get_by_summary_id(summary_id)

    def upsert_score(self, score: ScoreCreateRequest) -> None:
        return self._score.upsert(score,datetime.now(UTC))