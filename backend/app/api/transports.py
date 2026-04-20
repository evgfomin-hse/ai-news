import logging
import re
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_transport_service
from app.models import Transport, User
from app.schemas.transport import (
    CaptureHelloOut,
    SendMessageBody,
    SendMessageOut,
    TelegramTestOut,
    TransportOut,
    TransportPatch,
)
from app.services.transport_service import (
    TELEGRAM_CHAT_ID_KEY,
    TELEGRAM_TOKEN_KEY,
    TransportService,
    naive_utc_now,
    telegram_chat_id_from_row,
    telegram_token_from_row,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transports", tags=["transports"])


def _transport_out(row: Transport | None) -> TransportOut:
    if row is None:
        return TransportOut()
    return TransportOut(
        transportId=row.id,
        telegramConfigured=bool(telegram_token_from_row(row)),
        telegramChatId=telegram_chat_id_from_row(row),
    )


@router.get("", response_model=TransportOut)
def get_transport(
    user: Annotated[User, Depends(get_current_user)],
    transports: Annotated[TransportService, Depends(get_transport_service)],
) -> TransportOut:
    row = transports.get_active_for_user(user.id)
    return _transport_out(row)


@router.patch("", response_model=TransportOut)
def patch_transport(
    body: TransportPatch,
    user: Annotated[User, Depends(get_current_user)],
    transports: Annotated[TransportService, Depends(get_transport_service)],
) -> TransportOut:
    if body.telegramBotToken is None and body.telegramChatId is None:
        row = transports.get_active_for_user(user.id)
        return _transport_out(row)

    row = transports.ensure_active_for_user(user.id)
    blob = dict(row.data) if row.data is not None else {}

    if body.telegramBotToken is not None:
        stripped = body.telegramBotToken.strip()
        if stripped:
            blob[TELEGRAM_TOKEN_KEY] = stripped
        else:
            blob.pop(TELEGRAM_TOKEN_KEY, None)
            blob.pop(TELEGRAM_CHAT_ID_KEY, None)

    if body.telegramChatId is not None:
        s = str(body.telegramChatId).strip()
        if not s:
            blob[TELEGRAM_CHAT_ID_KEY] = None
        else:
            if not re.fullmatch(r"-?\d+", s):
                raise HTTPException(
                    status_code=400,
                    detail="telegramChatId must be a numeric Telegram chat id (groups may be negative).",
                )
            blob[TELEGRAM_CHAT_ID_KEY] = s

    row.data = blob
    row.updated_at = naive_utc_now()
    transports.persist_transport(row)
    return _transport_out(row)


@router.post("/telegram-test", response_model=TelegramTestOut)
def test_telegram_bot(
    user: Annotated[User, Depends(get_current_user)],
    transports: Annotated[TransportService, Depends(get_transport_service)],
) -> TelegramTestOut:
    row = transports.get_active_for_user(user.id)
    token = telegram_token_from_row(row)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Save a bot token first, then test.",
        )
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = requests.get(url, timeout=15)
    except requests.RequestException as exc:
        logger.warning("Telegram getMe request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach Telegram. Check the token and try again.",
        ) from exc
    try:
        payload = r.json()
    except ValueError:
        raise HTTPException(
            status_code=502, detail="Telegram returned a non-JSON response."
        ) from None
    if not payload.get("ok"):
        desc = payload.get("description") or "Unknown error"
        raise HTTPException(status_code=400, detail=f"Telegram: {desc}")
    result = payload.get("result") or {}
    bot_id = result.get("id")
    bot_id_int: int | None
    if isinstance(bot_id, int):
        bot_id_int = bot_id
    elif isinstance(bot_id, str) and bot_id.isdigit():
        bot_id_int = int(bot_id)
    else:
        bot_id_int = None
    return TelegramTestOut(
        ok=True,
        botUsername=result.get("username"),
        botId=bot_id_int,
    )


def _pick_hello_chat_from_updates(updates: list) -> tuple[int, str] | None:
    """Returns (update_id, chat_id_str) for the best matching hello message, or None."""
    candidates: list[tuple[int, str, str | None]] = []
    for u in updates:
        uid = u.get("update_id")
        if not isinstance(uid, int):
            continue
        msg = u.get("message") or u.get("edited_message")
        if not isinstance(msg, dict):
            continue
        text = (msg.get("text") or "").strip().lower()
        if text != "hello":
            continue
        chat = msg.get("chat")
        if not isinstance(chat, dict):
            continue
        cid = chat.get("id")
        if cid is None:
            continue
        chat_type = chat.get("type") if isinstance(chat.get("type"), str) else None
        candidates.append((uid, str(cid), chat_type))
    if not candidates:
        return None
    private = [c for c in candidates if c[2] == "private"]
    pool = private if private else candidates
    best = max(pool, key=lambda c: c[0])
    return best[0], best[1]


def _telegram_ack_updates(token: str, offset: int) -> None:
    try:
        requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": offset, "timeout": 0},
            timeout=15,
        )
    except requests.RequestException:
        logger.debug("Telegram ack getUpdates failed (non-fatal)", exc_info=True)


@router.post("/telegram-capture-hello", response_model=CaptureHelloOut)
def capture_hello_message(
    user: Annotated[User, Depends(get_current_user)],
    transports: Annotated[TransportService, Depends(get_transport_service)],
) -> CaptureHelloOut:
    row = transports.get_active_for_user(user.id)
    token = telegram_token_from_row(row)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Save a bot token first.",
        )
    existing = telegram_chat_id_from_row(row)
    if existing:
        return CaptureHelloOut(linked=True, chatId=existing, hint=None)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        r = requests.get(url, params={"limit": 100, "timeout": 0}, timeout=20)
    except requests.RequestException as exc:
        logger.warning("Telegram getUpdates failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach Telegram.",
        ) from exc
    try:
        payload = r.json()
    except ValueError:
        raise HTTPException(
            status_code=502, detail="Telegram returned a non-JSON response."
        ) from None
    if not payload.get("ok"):
        desc = str(payload.get("description") or "Unknown error")
        low = desc.lower()
        if "webhook" in low:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This bot has a webhook set; Telegram does not allow getUpdates. "
                    "Delete the webhook (BotFather /deleteWebhook or API) or enter chat id manually."
                ),
            )
        raise HTTPException(status_code=400, detail=f"Telegram: {desc}")

    updates = payload.get("result")
    if not isinstance(updates, list):
        updates = []
    picked = _pick_hello_chat_from_updates(updates)
    if picked is None:
        return CaptureHelloOut(
            linked=False,
            chatId=None,
            hint='No matching message yet. Open Telegram, open a chat with your bot, and send exactly: hello',
        )

    update_id, chat_id_str = picked
    row = transports.ensure_active_for_user(user.id)
    blob = dict(row.data) if row.data is not None else {}
    blob[TELEGRAM_CHAT_ID_KEY] = chat_id_str
    row.data = blob
    row.updated_at = naive_utc_now()
    transports.persist_transport(row)
    _telegram_ack_updates(token, update_id + 1)
    return CaptureHelloOut(
        linked=True,
        chatId=chat_id_str,
        hint=None,
    )


@router.post("/send-message", response_model=SendMessageOut)
def send_telegram_message(
    user: Annotated[User, Depends(get_current_user)],
    transports: Annotated[TransportService, Depends(get_transport_service)],
    body: SendMessageBody,
) -> SendMessageOut:
    row = transports.get_active_for_user(user.id)
    token = telegram_token_from_row(row)
    chat_id = telegram_chat_id_from_row(row)
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Configure a Telegram bot token first.",
        )
    if not chat_id:
        raise HTTPException(
            status_code=400,
            detail="Configure telegramChatId (your chat with the bot) before sending.",
        )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": body.text},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("Telegram sendMessage failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach Telegram.",
        ) from exc
    try:
        payload = r.json()
    except ValueError:
        raise HTTPException(
            status_code=502, detail="Telegram returned a non-JSON response."
        ) from None
    if not payload.get("ok"):
        desc = payload.get("description") or "Unknown error"
        raise HTTPException(status_code=400, detail=f"Telegram: {desc}")
    result = payload.get("result") or {}
    mid = result.get("message_id")
    if isinstance(mid, int):
        mid_int: int | None = mid
    elif isinstance(mid, str) and mid.isdigit():
        mid_int = int(mid)
    else:
        mid_int = None
    return SendMessageOut(ok=True, telegramMessageId=mid_int)
