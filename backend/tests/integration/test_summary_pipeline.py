"""End-to-end pipeline test: LLM + maintenance, providers stubbed.

Covers user-triggered (`append_placeholder_for_user`) and Telegram delivery
branches of the bulk pipeline. Bulk-path mechanics (interests gating, GDELT,
digest failure, prompt content) live in `test_summary_maintenance.py`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Interest, Summary, User
from app.services import summary_service
from app.services.summary_service import SummaryMaintenanceService
from app.services.telegram_service import TelegramSendError


class _FakeTransport:
    """Minimal Transport-row shape: only the `.data` attribute the helpers read."""

    def __init__(self, data: dict[str, Any] | None) -> None:
        self.data = data


class _StubTelegramSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.raise_on_send: Exception | None = None

    def send(self, *, token: str, chat_id: str, text: str) -> int | None:
        self.calls.append((token, chat_id, text))
        if self.raise_on_send is not None:
            raise self.raise_on_send
        return 42


def _patch_transport(monkeypatch, returner):
    """Override TransportService.get_active_for_user so tests don't need the JSONB table."""
    monkeypatch.setattr(
        summary_service.TransportService,
        "get_active_for_user",
        lambda self, user_id: returner(user_id),
    )


class _StubSummarizer:
    """Returns a deterministic body that echoes part of the prompt for assertions."""

    def __init__(self, body: str = "## Daily summary — fake\n\n- one bullet") -> None:
        self.body = body
        self.calls: list[str] = []

    def generate(self, *, prompt: str) -> str:
        self.calls.append(prompt)
        return self.body


def test_append_placeholder_for_user_uses_llm_when_configured(db: Session, user: User):
    summarizer = _StubSummarizer(body="## from-llm")
    maint = SummaryMaintenanceService(db, summarizer=summarizer)
    n = maint.append_placeholder_for_user(user.id)
    assert n == 1
    rows = db.query(Summary).filter_by(user_id=user.id).all()
    assert rows[-1].summary == "## from-llm"


def test_append_placeholder_for_user_falls_back_without_summarizer(db: Session, user: User):
    maint = SummaryMaintenanceService(db, summarizer=None)
    n = maint.append_placeholder_for_user(user.id)
    assert n == 1
    rows = db.query(Summary).filter_by(user_id=user.id).all()
    assert "Auto-generated" in (rows[-1].summary or "")


# ---------- Telegram delivery branch -----------------------------------------


def test_bulk_sends_summary_to_telegram_when_user_has_config(db: Session, user: User, monkeypatch):
    db.add(Interest(user_id=user.id, interests="AI"))
    db.commit()
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    summarizer = _StubSummarizer(body="## the-summary")
    maint = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=None,
        keyword_extractor=None,
        candidate_filter=None,
        telegram_sender=sender,
    )

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_sent"] == 1
    assert stats["telegram_skipped_no_config"] == 0
    assert stats["telegram_failed"] == 0
    assert sender.calls == [("tok", "100", "## the-summary")]


def test_bulk_skips_telegram_when_user_has_no_token_or_chat(db: Session, user: User, monkeypatch):
    db.add(Interest(user_id=user.id, interests="AI"))
    db.commit()
    _patch_transport(monkeypatch, lambda _uid: _FakeTransport(None))
    sender = _StubTelegramSender()
    maint = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=None,
        keyword_extractor=None,
        candidate_filter=None,
        telegram_sender=sender,
    )

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_skipped_no_config"] == 1
    assert stats["telegram_sent"] == 0
    assert sender.calls == []


def test_bulk_counts_telegram_failure_but_keeps_summary(db: Session, user: User, monkeypatch):
    db.add(Interest(user_id=user.id, interests="AI"))
    db.commit()
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    sender.raise_on_send = TelegramSendError("telegram_error", "Telegram: chat not found")
    maint = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=None,
        keyword_extractor=None,
        candidate_filter=None,
        telegram_sender=sender,
    )

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_failed"] == 1
    assert stats["telegram_sent"] == 0
    # The summary itself was still persisted before delivery.
    assert db.query(Summary).filter_by(user_id=user.id).count() == 1


def test_bulk_without_sender_counts_no_sender(db: Session, user: User):
    db.add(Interest(user_id=user.id, interests="AI"))
    db.commit()
    maint = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=None,
        keyword_extractor=None,
        candidate_filter=None,
        telegram_sender=None,
    )
    stats = maint.run_bulk_for_all_users()
    assert stats["telegram_no_sender"] == 1
    assert stats["telegram_sent"] == 0


def test_append_placeholder_for_user_also_sends_telegram(db: Session, user: User, monkeypatch):
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    summarizer = _StubSummarizer(body="## manual-generate")
    maint = SummaryMaintenanceService(db, summarizer=summarizer, telegram_sender=sender)
    maint.append_placeholder_for_user(user.id)
    assert sender.calls == [("tok", "100", "## manual-generate")]
