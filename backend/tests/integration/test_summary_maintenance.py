"""Integration tests for the rewritten daily news pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Interest, NewsArticle, User
from app.repositories.summary_repository import SummaryRepository
from app.services.gdelt_service import GdeltFetchError
from app.services.summary_service import (
    MockSummaryService,
    SummaryMaintenanceService,
    insert_generated_summary_for_user,
    run_summary_generation_for_all_users,
)


@dataclass
class _CountingFetcher:
    """Stand-in for `GdeltFetcherService` — records calls, returns a configured count."""

    return_count: int = 0
    raise_error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def fetch_and_store(self, *, query: str, start, end) -> int:
        self.calls.append({"query": query, "start": start, "end": end})
        if self.raise_error is not None:
            raise self.raise_error
        return self.return_count


@dataclass
class _StubKeywordExtractor:
    response: str | None
    calls: list[list[tuple[int, str]]] = field(default_factory=list)

    def extract(self, users_with_interests: list[tuple[int, str]]) -> str | None:
        self.calls.append(list(users_with_interests))
        return self.response


@dataclass
class _StubCandidateFilter:
    """Returns the first `top_n` articles unchanged (deterministic ordering for tests)."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def pick_top(self, *, interests_text: str, articles: list[NewsArticle], top_n: int):
        self.calls.append(
            {"interests_text": interests_text, "n_in": len(articles), "top_n": top_n}
        )
        return articles[:top_n]


@dataclass
class _StubSummarizer:
    """Returns the prompt back wrapped so tests can introspect; or raises on demand."""

    raise_error: Exception | None = None
    seen_prompts: list[str] = field(default_factory=list)

    def generate(self, *, prompt: str) -> str:
        self.seen_prompts.append(prompt)
        if self.raise_error is not None:
            raise self.raise_error
        return f"## Daily summary — wired\n\nbody for: {prompt[:30]}..."


def _add_interest(db: Session, user_id: int, text: str) -> None:
    db.add(Interest(user_id=user_id, interests=text))
    db.commit()


def test_users_without_interests_are_skipped(db: Session, user: User):
    other = User(google_id="g2", email="b@example.com")
    db.add(other)
    db.commit()
    _add_interest(db, user.id, "AI, robotics")  # only `user` has interests

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=_CountingFetcher(return_count=0),
        keyword_extractor=_StubKeywordExtractor(response="(AI OR robotics)"),
        candidate_filter=_StubCandidateFilter(),
        telegram_sender=None,
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["users_total"] == 2
    assert stats["users_processed"] == 1
    assert stats["skipped_no_interests"] == 1
    assert SummaryRepository(db).count_for_user(user.id) == 1
    assert SummaryRepository(db).count_for_user(other.id) == 0


def test_when_no_users_have_interests_keyword_extractor_and_gdelt_are_not_called(
    db: Session, user: User
):
    fetcher = _CountingFetcher()
    extractor = _StubKeywordExtractor(response="never used")

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=fetcher,
        keyword_extractor=extractor,
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["users_processed"] == 0
    assert stats["skipped_no_interests"] == 1
    assert fetcher.calls == []
    assert extractor.calls == []


def test_keyword_extractor_returning_none_skips_gdelt_but_still_calls_digest(
    db: Session, user: User
):
    _add_interest(db, user.id, "AI")
    fetcher = _CountingFetcher()

    summarizer = _StubSummarizer()
    svc = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=fetcher,
        keyword_extractor=_StubKeywordExtractor(response=None),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["keyword_extraction_failed"] == 1
    assert fetcher.calls == []
    # User with interests still gets a digest call (with empty news -> "no fresh news" body).
    assert stats["users_processed"] == 1
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_gdelt_fetch_error_is_swallowed_and_run_continues(db: Session, user: User):
    _add_interest(db, user.id, "AI")
    fetcher = _CountingFetcher(raise_error=GdeltFetchError("boom"))

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=fetcher,
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["gdelt_articles_fetched"] == 0
    assert stats["users_processed"] == 1


def test_user_with_interests_but_digest_failure_is_skipped_with_no_row(
    db: Session, user: User
):
    from app.services.llm_service import LLMError

    _add_interest(db, user.id, "AI")
    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(raise_error=LLMError("boom")),
        gdelt_fetcher=_CountingFetcher(),
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["digest_failed"] == 1
    assert stats["users_processed"] == 0
    assert SummaryRepository(db).count_for_user(user.id) == 0


def test_date_label_passed_to_prompt_is_yesterday(db: Session, user: User):
    _add_interest(db, user.id, "AI")
    summarizer = _StubSummarizer()
    svc = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=_CountingFetcher(),
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    svc.run_bulk_for_all_users()

    expected_yesterday = datetime.now(UTC).date() - timedelta(days=1)
    assert any(
        f"Today's date: {expected_yesterday.isoformat()}" in p for p in summarizer.seen_prompts
    )


# Preserved tests for unrelated helpers
def test_insert_generated_summary_for_user_returns_one(db: Session, user: User):
    assert insert_generated_summary_for_user(db, user.id) == 1
    db.commit()
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_run_summary_generation_for_all_users_reports_counts(db: Session, user: User):
    stats = run_summary_generation_for_all_users(db)
    db.commit()
    assert stats["users"] == 1
    assert stats["rows_inserted"] == 1


def test_mock_summary_service_returns_sample_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=1, page_size=5)
    assert resp.total > 0
    assert len(resp.items) == 5
    assert resp.generated_at is not None


def test_mock_summary_service_clamps_high_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=999, page_size=10)
    assert resp.page == resp.total_pages


def test_full_happy_path_news_flows_through_filter_into_prompt(db: Session, user: User):
    """End-to-end: pre-existing GDELT rows are picked up, filter narrows them, prompt shows them."""
    from datetime import timedelta

    _add_interest(db, user.id, "AI, robotics")

    # Pre-populate yesterday's news so we don't need GDELT to actually fetch.
    y_start = (datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
               - timedelta(days=1)).replace(tzinfo=None)
    for i in range(3):
        db.add(
            NewsArticle(
                fetched_at=y_start + timedelta(hours=2),
                source="gdelt:doc",
                title=f"AI headline {i}",
                description=None,
                url=f"https://example.test/ai{i}",
                published_at=y_start + timedelta(hours=1 + i),
            )
        )
    db.commit()

    summarizer = _StubSummarizer()
    filter_stub = _StubCandidateFilter()
    svc = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=_CountingFetcher(return_count=0),  # no new fetch needed; rows already exist
        keyword_extractor=_StubKeywordExtractor(response="(AI OR robotics)"),
        candidate_filter=filter_stub,
        telegram_sender=None,
    )
    stats = svc.run_bulk_for_all_users()

    # PerUserCandidateFilter was invoked once with the 3 pre-existing articles.
    assert len(filter_stub.calls) == 1
    assert filter_stub.calls[0]["n_in"] == 3
    assert filter_stub.calls[0]["interests_text"] == "AI, robotics"

    # Digest prompt contains the article titles (filter_stub returns articles unchanged).
    assert stats["users_processed"] == 1
    assert len(summarizer.seen_prompts) == 1
    prompt = summarizer.seen_prompts[0]
    for i in range(3):
        assert f"- AI headline {i}" in prompt
    # And the user's interests text.
    assert "AI, robotics" in prompt
