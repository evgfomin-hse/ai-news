"""End-to-end pipeline test: news fetcher + LLM + maintenance, both providers stubbed."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Score, Summary, User
from app.services import summary_service
from app.services.llm_service import LLMError
from app.services.news_service import NewsFetcherService
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


class _RaisingSummarizer:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def generate(self, *, prompt: str) -> str:
        self.calls += 1
        raise self.exc


def _build_fetcher(db: Session, articles_payload: list[dict[str, Any]]):
    payload = {"status": "ok", "articles": articles_payload}

    class _Response:
        def json(self) -> dict[str, Any]:
            return payload

    def _http_get(url, params=None, timeout=None) -> _Response:
        return _Response()

    return NewsFetcherService(db, api_key="k", http_get=_http_get)


def test_run_bulk_falls_back_to_placeholder_without_summarizer(db: Session, user: User):
    maint = SummaryMaintenanceService(db, summarizer=None, fetcher=None)
    stats = maint.run_bulk_for_all_users()
    assert stats["users"] == 1
    assert stats["rows_inserted"] == 1
    assert stats["llm_fallbacks"] == 1
    assert stats["llm_generated"] == 0
    rows = db.query(Summary).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert "Auto-generated" in (rows[0].summary or "")


def test_run_bulk_with_summarizer_inserts_llm_body(db: Session, user: User):
    summarizer = _StubSummarizer()
    maint = SummaryMaintenanceService(db, summarizer=summarizer, fetcher=None)
    stats = maint.run_bulk_for_all_users()
    assert stats["llm_generated"] == 1
    assert stats["llm_fallbacks"] == 0
    rows = db.query(Summary).filter_by(user_id=user.id).all()
    assert rows[0].summary == summarizer.body
    assert len(summarizer.calls) == 1
    # Prompt should include the "Today's news" section.
    assert "Today's news" in summarizer.calls[0]


def test_run_bulk_fallback_used_when_summarizer_raises(db: Session, user: User):
    summarizer = _RaisingSummarizer(LLMError("upstream busy"))
    maint = SummaryMaintenanceService(db, summarizer=summarizer, fetcher=None)
    stats = maint.run_bulk_for_all_users()
    assert stats["llm_generated"] == 0
    assert stats["llm_fallbacks"] == 1
    rows = db.query(Summary).filter_by(user_id=user.id).all()
    assert "Auto-generated" in (rows[0].summary or "")


def test_run_bulk_with_fetcher_persists_news_and_includes_them_in_prompt(db: Session, user: User):
    summarizer = _StubSummarizer()
    fetcher = _build_fetcher(
        db,
        [
            {
                "title": "World news today",
                "description": "Something happened",
                "url": "https://example.test/world",
                "publishedAt": "2026-05-23T10:15:00Z",
            }
        ],
    )
    maint = SummaryMaintenanceService(db, summarizer=summarizer, fetcher=fetcher)
    stats = maint.run_bulk_for_all_users()
    assert stats["news_fetched"] == 1
    assert "World news today" in summarizer.calls[0]


def test_pipeline_passes_interests_and_recent_scores_into_prompt(db: Session, user: User):
    from app.models import Interest

    db.add(Interest(user_id=user.id, interests="machine learning, hiking", updated_at=None))
    parent = Summary(user_id=user.id, summary="old", created_at=datetime(2024, 1, 1))
    db.add(parent)
    db.commit()
    db.add(
        Score(
            summary_id=parent.id,
            score=True,
            description="LLM coverage was great",
            updated_at=datetime(2024, 6, 1),
        )
    )
    db.commit()

    summarizer = _StubSummarizer()
    maint = SummaryMaintenanceService(db, summarizer=summarizer, fetcher=None)
    maint.run_bulk_for_all_users()
    prompt = summarizer.calls[0]
    assert "machine learning, hiking" in prompt
    assert "LIKED: LLM coverage was great" in prompt


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
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    summarizer = _StubSummarizer(body="## the-summary")
    maint = SummaryMaintenanceService(db, summarizer=summarizer, telegram_sender=sender)

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_sent"] == 1
    assert stats["telegram_skipped_no_config"] == 0
    assert stats["telegram_failed"] == 0
    assert sender.calls == [("tok", "100", "## the-summary")]


def test_bulk_skips_telegram_when_user_has_no_token_or_chat(db: Session, user: User, monkeypatch):
    _patch_transport(monkeypatch, lambda _uid: _FakeTransport(None))
    sender = _StubTelegramSender()
    maint = SummaryMaintenanceService(db, summarizer=_StubSummarizer(), telegram_sender=sender)

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_skipped_no_config"] == 1
    assert stats["telegram_sent"] == 0
    assert sender.calls == []


def test_bulk_counts_telegram_failure_but_keeps_summary(db: Session, user: User, monkeypatch):
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    sender.raise_on_send = TelegramSendError("telegram_error", "Telegram: chat not found")
    maint = SummaryMaintenanceService(db, summarizer=_StubSummarizer(), telegram_sender=sender)

    stats = maint.run_bulk_for_all_users()

    assert stats["telegram_failed"] == 1
    assert stats["telegram_sent"] == 0
    # The summary itself was still persisted.
    assert db.query(Summary).filter_by(user_id=user.id).count() == 1


def test_bulk_without_sender_counts_no_sender(db: Session, user: User):
    maint = SummaryMaintenanceService(db, summarizer=_StubSummarizer(), telegram_sender=None)
    stats = maint.run_bulk_for_all_users()
    assert stats["telegram_no_sender"] == 1
    assert stats["telegram_sent"] == 0


def test_bulk_delivers_placeholder_when_llm_fails(db: Session, user: User, monkeypatch):
    _patch_transport(
        monkeypatch,
        lambda _uid: _FakeTransport({"telegramBotToken": "tok", "telegramChatId": "100"}),
    )
    sender = _StubTelegramSender()
    summarizer = _RaisingSummarizer(LLMError("upstream busy"))
    maint = SummaryMaintenanceService(db, summarizer=summarizer, telegram_sender=sender)

    stats = maint.run_bulk_for_all_users()

    # LLM fallback was still delivered to Telegram (placeholder body).
    assert stats["llm_fallbacks"] == 1
    assert stats["telegram_sent"] == 1
    assert sender.calls[0][0] == "tok"
    assert "Auto-generated" in sender.calls[0][2]


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
