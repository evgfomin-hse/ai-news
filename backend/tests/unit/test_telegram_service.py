"""Unit tests for the Telegram sender. HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from app.services.telegram_service import (
    TELEGRAM_MAX_LEN,
    RequestsTelegramSender,
    TelegramSendError,
)


@dataclass
class _Resp:
    payload: Any
    status_code: int = 200

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _fake_post(response: _Resp):
    captured: dict[str, Any] = {}

    def _post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return response

    return _post, captured


def test_send_raises_network_on_request_exception():
    def _raise(*_a, **_k):
        raise requests.RequestException("boom")

    sender = RequestsTelegramSender(http_post=_raise)
    with pytest.raises(TelegramSendError) as exc:
        sender.send(token="t", chat_id="c", text="hi")
    assert exc.value.kind == "network"


def test_send_raises_non_json_on_value_error_from_json():
    post, _ = _fake_post(_Resp(ValueError("not json")))
    sender = RequestsTelegramSender(http_post=post)
    with pytest.raises(TelegramSendError) as exc:
        sender.send(token="t", chat_id="c", text="hi")
    assert exc.value.kind == "non_json"


def test_send_raises_telegram_error_when_payload_not_ok():
    post, _ = _fake_post(_Resp({"ok": False, "description": "chat not found"}))
    sender = RequestsTelegramSender(http_post=post)
    with pytest.raises(TelegramSendError) as exc:
        sender.send(token="t", chat_id="c", text="hi")
    assert exc.value.kind == "telegram_error"
    assert "chat not found" in exc.value.message


def test_send_raises_missing_message_id_when_result_not_dict():
    post, _ = _fake_post(_Resp({"ok": True, "result": "not a dict"}))
    sender = RequestsTelegramSender(http_post=post)
    with pytest.raises(TelegramSendError) as exc:
        sender.send(token="t", chat_id="c", text="hi")
    assert exc.value.kind == "missing_message_id"


def test_send_returns_message_id_on_success():
    post, captured = _fake_post(_Resp({"ok": True, "result": {"message_id": 42}}))
    sender = RequestsTelegramSender(http_post=post)
    mid = sender.send(token="bot-tok", chat_id="100", text="hello world")
    assert mid == 42
    assert captured["url"].endswith("/botbot-tok/sendMessage")
    assert captured["json"] == {"chat_id": "100", "text": "hello world"}


def test_send_returns_none_when_message_id_is_unrecognized_type():
    post, _ = _fake_post(_Resp({"ok": True, "result": {"message_id": 3.14}}))
    sender = RequestsTelegramSender(http_post=post)
    assert sender.send(token="t", chat_id="c", text="hi") is None


def test_send_returns_int_when_message_id_is_numeric_string():
    post, _ = _fake_post(_Resp({"ok": True, "result": {"message_id": "7"}}))
    sender = RequestsTelegramSender(http_post=post)
    assert sender.send(token="t", chat_id="c", text="hi") == 7


def test_send_truncates_text_when_over_limit_and_adds_hint():
    long = "a" * (TELEGRAM_MAX_LEN + 500)
    post, captured = _fake_post(_Resp({"ok": True, "result": {"message_id": 1}}))
    sender = RequestsTelegramSender(http_post=post)
    sender.send(token="t", chat_id="c", text=long)
    sent_text = captured["json"]["text"]
    assert len(sent_text) <= TELEGRAM_MAX_LEN
    assert sent_text.endswith("…(truncated)")


def test_send_does_not_truncate_text_under_limit():
    text = "x" * 4000
    post, captured = _fake_post(_Resp({"ok": True, "result": {"message_id": 1}}))
    sender = RequestsTelegramSender(http_post=post)
    sender.send(token="t", chat_id="c", text=text)
    assert captured["json"]["text"] == text
