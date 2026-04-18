from sqlalchemy.orm import Session

from app.models import Transport
from app.repositories.transports import TransportRepository
from app.services.transports import naive_utc_now


class TransportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transports = TransportRepository(session)

    def get_active_for_user(self, user_id: int) -> Transport | None:
        return self._transports.get_active_for_user(user_id)

    def ensure_active_for_user(self, user_id: int) -> Transport:
        return self._transports.ensure_active_for_user(user_id, now=naive_utc_now())

    def persist_transport(self, row: Transport) -> Transport:
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row
