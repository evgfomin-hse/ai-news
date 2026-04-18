from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transport


class TransportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_for_user(self, user_id: int) -> Transport | None:
        return self._session.scalar(
            select(Transport)
            .where(Transport.user_id == user_id, Transport.deleted_at.is_(None))
            .order_by(Transport.id.desc())
            .limit(1)
        )

    def ensure_active_for_user(self, user_id: int, *, now) -> Transport:
        row = self.get_active_for_user(user_id)
        if row is not None:
            return row
        row = Transport(
            user_id=user_id,
            data={},
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row
