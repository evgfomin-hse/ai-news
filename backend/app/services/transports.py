from datetime import UTC, datetime

from app.models import Transport

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
