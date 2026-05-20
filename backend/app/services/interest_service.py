from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.models import Interest
from app.repositories.interest_repository import InterestRepository


class InterestService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._interests = InterestRepository(session)

    def get_latest_for_user(self, user_id: int) -> Interest | None:
        return self._interests.get_latest_for_user(user_id)

    def upsert_for_user(self, user_id: int, *, interests_text: str) -> Interest:
        row = self._interests.upsert_interests(
            user_id,
            interests_text=interests_text.strip(),
            now=naive_utc_now(),
        )
        self._session.commit()
        return row
