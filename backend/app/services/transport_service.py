from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Transport
from app.repositories.transport_repository import TransportRepository

TELEGRAM_TOKEN_KEY = "telegramBotToken"
TELEGRAM_CHAT_ID_KEY = "telegramChatId"


def naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def telegram_token_from_row(row: Transport | None) -> str:
    if row is None or row.data is None:
        return ""
    raw = row.data.get(TELEGRAM_TOKEN_KEY)
    return raw.strip() if isinstance(raw, str) else ""


def telegram_chat_id_from_row(row: Transport | None) -> str | None:
    """Returns normalized chat id string, or None if unset / null."""
    if row is None or row.data is None:
        return None
    raw = row.data.get(TELEGRAM_CHAT_ID_KEY)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        return str(int(raw))
    if isinstance(raw, str):
        s = raw.strip()
        return s if s else None
    return None


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
