"""Pure unit tests for transport helpers — no DB, no HTTP."""

from types import SimpleNamespace

import pytest

from app.api.transports import _pick_hello_chat_from_updates
from app.services.transport_service import (
    TELEGRAM_CHAT_ID_KEY,
    TELEGRAM_TOKEN_KEY,
    telegram_chat_id_from_row,
    telegram_token_from_row,
)


def _row(data):
    """Build a transport-like row without touching the ORM."""
    return SimpleNamespace(data=data)


class TestTelegramTokenFromRow:
    def test_none_row_returns_empty(self):
        assert telegram_token_from_row(None) == ""

    def test_missing_data_returns_empty(self):
        assert telegram_token_from_row(_row(None)) == ""

    def test_strips_whitespace(self):
        assert telegram_token_from_row(_row({TELEGRAM_TOKEN_KEY: "  abc  "})) == "abc"

    def test_non_string_returns_empty(self):
        assert telegram_token_from_row(_row({TELEGRAM_TOKEN_KEY: 123})) == ""


class TestTelegramChatIdFromRow:
    def test_none_row(self):
        assert telegram_chat_id_from_row(None) is None

    def test_explicit_null(self):
        assert telegram_chat_id_from_row(_row({TELEGRAM_CHAT_ID_KEY: None})) is None

    def test_int_is_stringified(self):
        assert telegram_chat_id_from_row(_row({TELEGRAM_CHAT_ID_KEY: -100})) == "-100"

    def test_float_is_truncated(self):
        assert telegram_chat_id_from_row(_row({TELEGRAM_CHAT_ID_KEY: 42.0})) == "42"

    def test_blank_string_returns_none(self):
        assert telegram_chat_id_from_row(_row({TELEGRAM_CHAT_ID_KEY: "   "})) is None

    def test_bool_is_rejected(self):
        # `bool` is an `int` subclass — we must not let `True` masquerade as chat id "1".
        assert telegram_chat_id_from_row(_row({TELEGRAM_CHAT_ID_KEY: True})) is None


class TestPickHelloChatFromUpdates:
    def _msg(self, *, update_id, text, chat_id=42, chat_type="private", edited=False):
        key = "edited_message" if edited else "message"
        return {
            "update_id": update_id,
            key: {"text": text, "chat": {"id": chat_id, "type": chat_type}},
        }

    def test_empty_updates_returns_none(self):
        assert _pick_hello_chat_from_updates([]) is None

    def test_ignores_non_hello_text(self):
        assert _pick_hello_chat_from_updates([self._msg(update_id=1, text="hi")]) is None

    def test_hello_is_case_insensitive_and_trimmed(self):
        result = _pick_hello_chat_from_updates([self._msg(update_id=1, text="  Hello  ")])
        assert result == (1, "42")

    def test_picks_latest_update_id(self):
        updates = [
            self._msg(update_id=1, text="hello", chat_id=11),
            self._msg(update_id=5, text="hello", chat_id=55),
            self._msg(update_id=3, text="hello", chat_id=33),
        ]
        assert _pick_hello_chat_from_updates(updates) == (5, "55")

    def test_prefers_private_over_group(self):
        updates = [
            self._msg(update_id=10, text="hello", chat_id=-1, chat_type="group"),
            self._msg(update_id=2, text="hello", chat_id=7, chat_type="private"),
        ]
        assert _pick_hello_chat_from_updates(updates) == (2, "7")

    def test_accepts_edited_message(self):
        result = _pick_hello_chat_from_updates(
            [self._msg(update_id=9, text="hello", chat_id=8, edited=True)]
        )
        assert result == (9, "8")

    @pytest.mark.parametrize(
        "broken",
        [
            {"update_id": "x", "message": {"text": "hello", "chat": {"id": 1}}},
            {"update_id": 1, "message": "not-a-dict"},
            {"update_id": 1, "message": {"text": "hello", "chat": "not-a-dict"}},
            {"update_id": 1, "message": {"text": "hello", "chat": {"id": None}}},
        ],
    )
    def test_malformed_updates_are_skipped(self, broken):
        assert _pick_hello_chat_from_updates([broken]) is None
