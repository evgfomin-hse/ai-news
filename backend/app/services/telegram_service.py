"""Telegram sendMessage wrapper. Shared by the per-user pipeline and the manual API route."""

from __future__ import annotations

import logging
from typing import Literal, Protocol

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
# Telegram caps a single sendMessage at 4096 chars. We truncate just below to leave room
# for a hint ellipsis so the user sees that the message was clipped.
TELEGRAM_MAX_LEN = 4096
_TRUNCATION_HINT = "\n\n…(truncated)"


SendErrorKind = Literal["network", "non_json", "telegram_error", "missing_message_id"]


class TelegramSendError(RuntimeError):
    """Raised when a Telegram sendMessage call cannot complete."""

    def __init__(self, kind: SendErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class TelegramSender(Protocol):
    """Strategy boundary so the pipeline + API route can be tested without HTTP."""

    def send(self, *, token: str, chat_id: str, text: str) -> int | None: ...


def _truncate(text: str, *, max_len: int = TELEGRAM_MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    # Leave headroom for the hint so the result is still under the cap.
    head = text[: max_len - len(_TRUNCATION_HINT)]
    return head + _TRUNCATION_HINT


def _coerce_message_id(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


class RequestsTelegramSender:
    """HTTP-backed sender; uses `requests.post` to Telegram's sendMessage endpoint."""

    def __init__(self, *, timeout_seconds: int = 15, http_post=None) -> None:
        # Default to None (not `requests.post`) so test monkeypatches of `requests.post`
        # land — we look the callable up at send time, not at construction time.
        self._timeout_seconds = timeout_seconds
        self._http_post = http_post

    def send(self, *, token: str, chat_id: str, text: str) -> int | None:
        body = _truncate(text)
        url = TELEGRAM_API_TEMPLATE.format(token=token)
        post = self._http_post if self._http_post is not None else requests.post
        try:
            r = post(
                url,
                json={"chat_id": chat_id, "text": body},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning("Telegram sendMessage failed: %s", exc)
            raise TelegramSendError("network", "Could not reach Telegram") from exc

        try:
            payload = r.json()
        except ValueError as exc:
            raise TelegramSendError("non_json", "Telegram returned a non-JSON response") from exc

        if not payload.get("ok"):
            description = payload.get("description") or "Unknown error"
            raise TelegramSendError("telegram_error", f"Telegram: {description}")

        result = payload.get("result")
        if not isinstance(result, dict):
            raise TelegramSendError(
                "missing_message_id", "Telegram response missing result.message_id"
            )
        return _coerce_message_id(result.get("message_id"))
