"""Transport routes — TransportService and `requests` are stubbed.

The Transport ORM uses Postgres JSONB and cannot be exercised against in-memory
SQLite, so we substitute an in-memory transport store at the dependency boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api import transports as transports_api
from app.api.dependencies import get_transport_service
from app.main import app


@dataclass
class _Row:
    id: int = 1
    data: dict[str, Any] = field(default_factory=dict)
    updated_at: Any = None


class _StubTransportService:
    def __init__(self) -> None:
        self.row: _Row | None = None

    def get_active_for_user(self, user_id: int) -> _Row | None:
        return self.row

    def ensure_active_for_user(self, user_id: int) -> _Row:
        if self.row is None:
            self.row = _Row()
        return self.row

    def persist_transport(self, row: _Row) -> _Row:
        self.row = row
        return row


@dataclass
class _Resp:
    """Mimics enough of `requests.Response` for our routes."""

    payload: Any
    raise_exc: Exception | None = None

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


@pytest.fixture
def stub_transports():
    stub = _StubTransportService()
    app.dependency_overrides[get_transport_service] = lambda: stub
    try:
        yield stub
    finally:
        app.dependency_overrides.pop(get_transport_service, None)


@pytest.fixture
def fake_requests(monkeypatch):
    """Replace `requests.get`/`requests.post` inside the route module."""
    calls: dict[str, list] = {"get": [], "post": []}
    responses: dict[str, Any] = {}

    def _fake_get(url, params=None, timeout=None):
        calls["get"].append((url, params))
        return responses.get("get", _Resp({"ok": True, "result": {}}))

    def _fake_post(url, json=None, timeout=None):
        calls["post"].append((url, json))
        return responses.get("post", _Resp({"ok": True, "result": {}}))

    monkeypatch.setattr(transports_api.requests, "get", _fake_get)
    monkeypatch.setattr(transports_api.requests, "post", _fake_post)
    return calls, responses


# ---------- GET /transports ----------------------------------------------------

def test_get_returns_empty_when_no_transport(
    authed_client: TestClient, stub_transports
):
    resp = authed_client.get("/transports")
    assert resp.status_code == 200
    assert resp.json() == {
        "transportId": None,
        "telegramConfigured": False,
        "telegramChatId": None,
    }


def test_get_reflects_configured_telegram(
    authed_client: TestClient, stub_transports
):
    stub_transports.row = _Row(
        id=7,
        data={"telegramBotToken": "abc", "telegramChatId": "123"},
    )
    body = authed_client.get("/transports").json()
    assert body == {"transportId": 7, "telegramConfigured": True, "telegramChatId": "123"}


# ---------- PATCH /transports --------------------------------------------------

def test_patch_no_fields_returns_current_state(
    authed_client: TestClient, stub_transports
):
    resp = authed_client.patch("/transports", json={})
    assert resp.status_code == 200
    assert resp.json()["telegramConfigured"] is False


def test_patch_saves_token_and_chat_id(authed_client: TestClient, stub_transports):
    resp = authed_client.patch(
        "/transports",
        json={"telegramBotToken": " tok ", "telegramChatId": "100"},
    )
    assert resp.status_code == 200
    assert stub_transports.row.data["telegramBotToken"] == "tok"
    assert stub_transports.row.data["telegramChatId"] == "100"


def test_patch_blank_token_clears_token_and_chat(
    authed_client: TestClient, stub_transports
):
    stub_transports.row = _Row(
        data={"telegramBotToken": "old", "telegramChatId": "100"}
    )
    resp = authed_client.patch("/transports", json={"telegramBotToken": "   "})
    assert resp.status_code == 200
    assert "telegramBotToken" not in stub_transports.row.data
    assert "telegramChatId" not in stub_transports.row.data


def test_patch_rejects_non_numeric_chat_id(
    authed_client: TestClient, stub_transports
):
    resp = authed_client.patch("/transports", json={"telegramChatId": "abc"})
    assert resp.status_code == 400


# ---------- POST /transports/telegram-test ------------------------------------

def test_telegram_test_requires_token(authed_client: TestClient, stub_transports):
    resp = authed_client.post("/transports/telegram-test")
    assert resp.status_code == 400


def test_telegram_test_returns_bot_info(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp({"ok": True, "result": {"id": 42, "username": "mybot"}})

    resp = authed_client.post("/transports/telegram-test")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "botUsername": "mybot", "botId": 42}


def test_telegram_test_502_on_network_error(
    authed_client: TestClient, stub_transports, monkeypatch
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})

    def _raise(*_a, **_k):
        raise transports_api.requests.RequestException("boom")

    monkeypatch.setattr(transports_api.requests, "get", _raise)
    resp = authed_client.post("/transports/telegram-test")
    assert resp.status_code == 502


def test_telegram_test_400_when_telegram_says_not_ok(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp({"ok": False, "description": "Unauthorized"})

    resp = authed_client.post("/transports/telegram-test")
    assert resp.status_code == 400
    assert "Unauthorized" in resp.json()["detail"]


def test_telegram_test_502_on_non_json(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp(ValueError("not json"))

    resp = authed_client.post("/transports/telegram-test")
    assert resp.status_code == 502


# ---------- POST /transports/telegram-capture-hello ---------------------------

def test_capture_hello_requires_token(authed_client: TestClient, stub_transports):
    resp = authed_client.post("/transports/telegram-capture-hello")
    assert resp.status_code == 400


def test_capture_hello_returns_existing_link(
    authed_client: TestClient, stub_transports
):
    stub_transports.row = _Row(
        data={"telegramBotToken": "tok", "telegramChatId": "777"}
    )
    resp = authed_client.post("/transports/telegram-capture-hello")
    assert resp.status_code == 200
    assert resp.json() == {"linked": True, "chatId": "777", "hint": None}


def test_capture_hello_finds_and_persists_chat(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp(
        {
            "ok": True,
            "result": [
                {
                    "update_id": 9,
                    "message": {
                        "text": "hello",
                        "chat": {"id": 555, "type": "private"},
                    },
                }
            ],
        }
    )

    resp = authed_client.post("/transports/telegram-capture-hello")
    assert resp.status_code == 200
    assert resp.json() == {"linked": True, "chatId": "555", "hint": None}
    assert stub_transports.row.data["telegramChatId"] == "555"


def test_capture_hello_returns_hint_when_no_match(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp({"ok": True, "result": []})

    body = authed_client.post("/transports/telegram-capture-hello").json()
    assert body["linked"] is False
    assert body["chatId"] is None
    assert "hello" in body["hint"]


def test_capture_hello_409_when_webhook_set(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    _, responses = fake_requests
    responses["get"] = _Resp(
        {"ok": False, "description": "Conflict: can't use getUpdates with webhook"}
    )

    resp = authed_client.post("/transports/telegram-capture-hello")
    assert resp.status_code == 409


# ---------- POST /transports/send-message -------------------------------------

def test_send_message_requires_token(authed_client: TestClient, stub_transports):
    resp = authed_client.post("/transports/send-message", json={"text": "hi"})
    assert resp.status_code == 400


def test_send_message_requires_chat_id(authed_client: TestClient, stub_transports):
    stub_transports.row = _Row(data={"telegramBotToken": "tok"})
    resp = authed_client.post("/transports/send-message", json={"text": "hi"})
    assert resp.status_code == 400
    assert "chat" in resp.json()["detail"].lower()


def test_send_message_success(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(
        data={"telegramBotToken": "tok", "telegramChatId": "100"}
    )
    _, responses = fake_requests
    responses["post"] = _Resp({"ok": True, "result": {"message_id": 7}})

    resp = authed_client.post("/transports/send-message", json={"text": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "telegramMessageId": 7}


def test_send_message_400_when_telegram_rejects(
    authed_client: TestClient, stub_transports, fake_requests
):
    stub_transports.row = _Row(
        data={"telegramBotToken": "tok", "telegramChatId": "100"}
    )
    _, responses = fake_requests
    responses["post"] = _Resp({"ok": False, "description": "chat not found"})

    resp = authed_client.post("/transports/send-message", json={"text": "hi"})
    assert resp.status_code == 400


def test_send_message_502_on_network_error(
    authed_client: TestClient, stub_transports, monkeypatch
):
    stub_transports.row = _Row(
        data={"telegramBotToken": "tok", "telegramChatId": "100"}
    )

    def _raise(*_a, **_k):
        raise transports_api.requests.RequestException("boom")

    monkeypatch.setattr(transports_api.requests, "post", _raise)
    resp = authed_client.post("/transports/send-message", json={"text": "hi"})
    assert resp.status_code == 502


def test_transports_endpoints_require_auth(client: TestClient):
    assert client.get("/transports").status_code == 401
    assert client.patch("/transports", json={}).status_code == 401
    assert client.post("/transports/telegram-test").status_code == 401
    assert client.post("/transports/telegram-capture-hello").status_code == 401
    assert client.post("/transports/send-message", json={"text": "x"}).status_code == 401
