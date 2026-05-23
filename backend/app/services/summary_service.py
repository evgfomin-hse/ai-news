"""User summaries: read from `public.summaries`, placeholder generation, and maintenance."""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.repositories.interest_repository import InterestRepository
from app.repositories.news_repository import NewsRepository
from app.repositories.score_repository import ScoreRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.summary import SummaryItem, UserSummaryResponse
from app.services.llm_service import LLMError, LLMSummarizer
from app.services.news_service import NewsFetchError, NewsFetcherService
from app.services.summary_prompt import (
    build_summary_prompt,
    news_items_from_rows,
    score_signals_from_rows,
)
from app.services.telegram_service import TelegramSender, TelegramSendError
from app.services.transport_service import (
    TransportService,
    telegram_chat_id_from_row,
    telegram_token_from_row,
)

logger = logging.getLogger(__name__)

# How many of the user's most recent scored summaries feed into the prompt.
RECENT_SCORES_LIMIT = 10
# News rows fetched no more than this many hours ago count as "today's news".
NEWS_FRESHNESS_HOURS = 36


class SummaryService(ABC):
    """Application port for user-scoped summaries (swap mock / LLM / DB implementations)."""

    @abstractmethod
    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        """Return a page of summary rows plus pagination metadata."""


def _total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class PostgresSummaryService(SummaryService):
    """Loads markdown rows from coursework `public.summaries` with offset pagination."""

    EMPTY_NOTICE = """## No summaries yet

Take a deep breath, you can configure your interests and transport channel"""

    def __init__(self, summaries: SummaryRepository) -> None:
        self._summaries = summaries

    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        total = self._summaries.count_for_user(user_id)
        tp = _total_pages(total, page_size)

        if total == 0:
            return UserSummaryResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                generated_at=None,
                notice=self.EMPTY_NOTICE,
            )

        safe_page = min(max(page, 1), tp)
        offset = (safe_page - 1) * page_size

        rows = self._summaries.list_page_for_user(user_id, offset=offset, limit=page_size)

        items: list[SummaryItem] = []
        latest: datetime | None = None
        for row in rows:
            ca = row.created_at
            if ca is not None and (latest is None or ca > latest):
                latest = ca
            title = "Summary" if ca is None else ca.strftime("%Y-%m-%d %H:%M")
            body = (row.summary or "").strip()
            items.append(SummaryItem(id=str(row.id), title=title, body=body))

        generated = _as_utc(latest) if latest is not None else None

        return UserSummaryResponse(
            items=items,
            total=total,
            page=safe_page,
            page_size=page_size,
            total_pages=tp,
            generated_at=generated,
            notice="",
        )


class MockSummaryService(SummaryService):
    """In-memory paginated sample (not wired in dependencies by default)."""

    EMPTY_NOTICE = """## No summary sections yet

The mock has **no items** for this request. When sections exist, they render as markdown below."""

    _SAMPLE_BODY = "\n".join(
        [
            "## Hello from the mock summary",
            "",
            "This line mixes **bold**, *italic*, and `inline code`.",
            "",
            "- First bullet",
            "- Second bullet with a [link](https://example.org)",
            "",
            "> A short blockquote for styling checks.",
            "",
            "| Feature | Status |",
            "|---------|--------|",
            "| Markdown | OK |",
        ]
    )

    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        _ = user_id
        all_items = [
            SummaryItem(
                id=f"mock-{i}",
                title=f"Sample {i}",
                body=self._SAMPLE_BODY if i == 1 else f"Body **{i}**",
            )
            for i in range(1, 48)
        ]
        total = len(all_items)
        tp = _total_pages(total, page_size)
        safe_page = min(max(page, 1), max(tp, 1))
        offset = (safe_page - 1) * page_size
        slice_items = all_items[offset : offset + page_size]
        return UserSummaryResponse(
            items=slice_items,
            total=total,
            page=safe_page,
            page_size=page_size,
            total_pages=tp,
            generated_at=datetime.now(UTC),
            notice=self.EMPTY_NOTICE if total == 0 else "",
        )


BODY_TEMPLATE = """## Daily summary — {date}

_Auto-generated._ Wire your own pipeline (LLM, News API, DB rollups) to replace this placeholder.
"""


def _placeholder_body() -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return BODY_TEMPLATE.format(date=stamp)


def _append_placeholder_row(summaries: SummaryRepository, user_id: int) -> None:
    summaries.append_row(
        user_id=user_id,
        summary=_placeholder_body(),
        created_at=naive_utc_now(),
    )


def insert_generated_summary_for_user(db: Session, user_id: int) -> int:
    """Appends one `summaries` row for `user_id`. Returns number of rows inserted (0 or 1)."""
    _append_placeholder_row(SummaryRepository(db), user_id)
    return 1


def run_summary_generation_for_all_users(db: Session) -> dict[str, int]:
    """Placeholder-only path (used as fallback when the real pipeline is unavailable)."""
    users = UserRepository(db)
    summaries = SummaryRepository(db)
    user_ids = users.list_all_ids()
    for uid in user_ids:
        _append_placeholder_row(summaries, uid)
    return {"users": len(user_ids), "rows_inserted": len(user_ids)}


def _generate_one_for_user(
    *,
    user_id: int,
    today_label: str,
    interests: InterestRepository,
    scores: ScoreRepository,
    news: NewsRepository,
    summaries: SummaryRepository,
    summarizer: LLMSummarizer,
) -> str | None:
    """Build the prompt + call the LLM + insert one summary row.

    Returns the generated summary body on success, or None if the LLM call failed
    (the caller should fall back to the placeholder path).
    """
    interest_row = interests.get_latest_for_user(user_id)
    interest_text = interest_row.interests if interest_row is not None else None
    recent_scores = scores.list_recent_for_user(user_id, limit=RECENT_SCORES_LIMIT)
    news_rows = news.list_since(
        since=naive_utc_now() - timedelta(hours=NEWS_FRESHNESS_HOURS),
        limit=50,
    )

    prompt = build_summary_prompt(
        today_label=today_label,
        interests_text=interest_text,
        recent_scores=score_signals_from_rows(recent_scores),
        news=news_items_from_rows(news_rows),
    )
    try:
        body = summarizer.generate(prompt=prompt)
    except LLMError as exc:
        logger.warning("LLM failed for user_id=%s: %s", user_id, exc)
        return None

    summaries.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
    return body


# Outcome of the Telegram delivery attempt for one user. Used for stats.
TelegramOutcome = Literal["sent", "skipped_no_config", "failed", "no_sender"]


def _deliver_to_telegram(
    *,
    user_id: int,
    body: str,
    transports: TransportService,
    sender: TelegramSender | None,
) -> TelegramOutcome:
    """Try to send `body` to the user's configured Telegram chat.

    Errors are swallowed (the summary is already persisted; delivery is best-effort).
    Returns a stat tag the caller uses to build aggregate counts.
    """
    from sqlalchemy.exc import SQLAlchemyError

    if sender is None:
        return "no_sender"
    try:
        row = transports.get_active_for_user(user_id)
    except SQLAlchemyError as exc:
        logger.warning("Transport lookup failed for user_id=%s: %s", user_id, exc)
        return "skipped_no_config"
    token = telegram_token_from_row(row)
    chat_id = telegram_chat_id_from_row(row)
    if not token or not chat_id:
        return "skipped_no_config"
    try:
        sender.send(token=token, chat_id=chat_id, text=body)
    except TelegramSendError as exc:
        logger.warning("Telegram send failed for user_id=%s: %s", user_id, exc)
        return "failed"
    return "sent"


class SummaryMaintenanceService:
    """Write-side summary operations.

    Real pipeline:
      1. (bulk only) fetch today's news via `fetcher` if one is configured.
      2. for each user, build a prompt from interests + recent scores + today's news,
         call `summarizer`, and insert one `summaries` row.
      3. send the resulting summary to the user's Telegram chat via `telegram_sender`
         if both are configured. Delivery failures are logged + counted, never fatal.
      4. on any LLM error, fall back to inserting the placeholder row for that user
         (and still attempt Telegram delivery of the placeholder).
    """

    def __init__(
        self,
        session: Session,
        *,
        summarizer: LLMSummarizer | None = None,
        fetcher: NewsFetcherService | None = None,
        telegram_sender: TelegramSender | None = None,
    ) -> None:
        self._session = session
        self._summarizer = summarizer
        self._fetcher = fetcher
        self._telegram_sender = telegram_sender

    def _components(
        self,
    ) -> tuple[
        InterestRepository,
        ScoreRepository,
        NewsRepository,
        SummaryRepository,
        TransportService,
    ]:
        return (
            InterestRepository(self._session),
            ScoreRepository(self._session),
            NewsRepository(self._session),
            SummaryRepository(self._session),
            TransportService(self._session),
        )

    def append_placeholder_for_user(self, user_id: int) -> int:
        """User-triggered POST /summary/generate. Uses the real pipeline when configured.

        Does NOT fetch news (that's a bulk-job responsibility). Uses whatever news rows
        the daily job has most recently stored. Falls back to placeholder on LLM error
        or when no summarizer is configured. The resulting summary is also pushed to
        the user's Telegram chat when both a sender and a configured transport exist.
        """
        today_label = datetime.now(UTC).strftime("%Y-%m-%d")
        interests, scores, news, summaries, transports = self._components()
        if self._summarizer is None:
            body = _placeholder_body()
            summaries.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
        else:
            body = _generate_one_for_user(
                user_id=user_id,
                today_label=today_label,
                interests=interests,
                scores=scores,
                news=news,
                summaries=summaries,
                summarizer=self._summarizer,
            )
            if body is None:
                body = _placeholder_body()
                summaries.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
        _deliver_to_telegram(
            user_id=user_id,
            body=body,
            transports=transports,
            sender=self._telegram_sender,
        )
        self._session.commit()
        return 1

    def run_bulk_for_all_users(self) -> dict[str, int]:
        """Nightly job entry point. Fetch news, generate one summary per user, deliver."""
        users = UserRepository(self._session)
        interests, scores, news, summaries, transports = self._components()

        news_inserted = 0
        if self._fetcher is not None:
            try:
                news_inserted = self._fetcher.fetch_and_store()
            except NewsFetchError as exc:
                logger.warning("News fetch failed; continuing with stale articles: %s", exc)

        user_ids = users.list_all_ids()
        today_label = datetime.now(UTC).strftime("%Y-%m-%d")
        generated = 0
        fallbacks = 0
        delivery_counts: dict[TelegramOutcome, int] = {
            "sent": 0,
            "skipped_no_config": 0,
            "failed": 0,
            "no_sender": 0,
        }
        for uid in user_ids:
            if self._summarizer is None:
                body = _placeholder_body()
                summaries.append_row(user_id=uid, summary=body, created_at=naive_utc_now())
                fallbacks += 1
            else:
                body = _generate_one_for_user(
                    user_id=uid,
                    today_label=today_label,
                    interests=interests,
                    scores=scores,
                    news=news,
                    summaries=summaries,
                    summarizer=self._summarizer,
                )
                if body is None:
                    body = _placeholder_body()
                    summaries.append_row(user_id=uid, summary=body, created_at=naive_utc_now())
                    fallbacks += 1
                else:
                    generated += 1
            outcome = _deliver_to_telegram(
                user_id=uid,
                body=body,
                transports=transports,
                sender=self._telegram_sender,
            )
            delivery_counts[outcome] += 1
        self._session.commit()
        return {
            "users": len(user_ids),
            "rows_inserted": len(user_ids),
            "news_fetched": news_inserted,
            "llm_generated": generated,
            "llm_fallbacks": fallbacks,
            "telegram_sent": delivery_counts["sent"],
            "telegram_skipped_no_config": delivery_counts["skipped_no_config"],
            "telegram_failed": delivery_counts["failed"],
            "telegram_no_sender": delivery_counts["no_sender"],
        }


__all__ = [
    "MockSummaryService",
    "PostgresSummaryService",
    "SummaryMaintenanceService",
    "SummaryService",
    "insert_generated_summary_for_user",
    "run_summary_generation_for_all_users",
]
