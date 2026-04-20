from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Interest


class InterestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest_for_user(self, user_id: int) -> Interest | None:
        return self._session.scalar(
            select(Interest)
            .where(Interest.user_id == user_id)
            .order_by(Interest.id.desc())
            .limit(1)
        )

    def upsert_interests(
        self,
        user_id: int,
        *,
        interests_text: str,
        now,
    ) -> Interest:
        row = self.get_latest_for_user(user_id)
        if row is None:
            row = Interest(
                user_id=user_id,
                interests=interests_text or None,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.interests = interests_text or None
            row.updated_at = now
            self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row
