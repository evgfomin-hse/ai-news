from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transport

TELEGRAM_TOKEN_KEY = "telegramBotToken"
TELEGRAM_CHAT_ID_KEY = "telegramChatId"


def naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_active_transport(db: Session, user_id: int) -> Transport | None:
    return db.scalar(
        select(Transport)
        .where(Transport.user_id == user_id, Transport.deleted_at.is_(None))
        .order_by(Transport.id.desc())
        .limit(1)
    )


def ensure_transport(db: Session, user_id: int) -> Transport:
    row = get_active_transport(db, user_id)
    if row is not None:
        return row
    row = Transport(
        user_id=user_id,
        data={},
        created_at=naive_utc_now(),
        updated_at=naive_utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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
