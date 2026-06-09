"""User summaries: read from `public.summaries`, placeholder generation, and maintenance."""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import naive_utc_now
from app.repositories.interest_repository import InterestRepository
from app.repositories.news_repository import NewsRepository
from app.repositories.score_repository import ScoreRepository
from app.repositories.summary_repository import SummaryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.summary import SummaryItem, UserSummaryResponse
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.news_service import NewsApiFetcherService, NewsFetchError
from app.services.keyword_extractor import KeywordExtractor
from app.services.llm_service import LLMError, LLMSummarizer
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


def _previous_day_window(now: datetime) -> tuple[datetime, datetime, str]:
    """Return (yesterday_start, yesterday_end, date_label) for a given run time.

    `now` is expected to be timezone-aware UTC; we use the UTC-day calendar.
    """
    today_midnight = datetime(now.year, now.month, now.day, tzinfo=UTC)
    start = today_midnight - timedelta(days=1)
    end = start + timedelta(hours=23, minutes=59, seconds=59)
    return start, end, start.strftime("%Y-%m-%d")


def _users_with_interests(users, interests) -> list[tuple[int, str]]:
    """Returns (user_id, interests_text) for users whose latest interests row is non-empty.

    Users with no interests row, or an empty/whitespace `interests` field, are excluded.
    Order mirrors `users.list_all_ids()`.

    Reads `row.interests` (the real model field) with fallback to `row.text` so the
    fake repos in tests can use a simpler field name.
    """
    out: list[tuple[int, str]] = []
    for uid in users.list_all_ids():
        row = interests.get_latest_for_user(uid)
        if row is None:
            continue
        text = (row.interests if hasattr(row, "interests") else getattr(row, "text", None)) or ""
        text = text.strip()
        if not text:
            continue
        out.append((uid, text))
    return out


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
        date_label=today_label,
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

    Bulk path (nightly, previous-day digest):
      1. extract a global keyword query from all users' interests (one LLM call via `keyword_extractor`).
      2. fetch yesterday's news from NewsAPI using that query (`news_fetcher`), persisting to `news_articles`.
      3. for each user with non-empty interests, narrow the day's pool via chunked LLM calls
         (`candidate_filter`), then generate a digest via `summarizer` and insert one `summaries` row.
      4. deliver the digest to the user's Telegram chat via `telegram_sender` when configured.

      Users without interests are skipped. Users whose digest LLM call fails are also skipped:
      no `summaries` row, no Telegram delivery. Delivery failures are logged + counted, never fatal.

    User-triggered path (`append_placeholder_for_user`):
      LLM-generates a fresh digest "now" from the rolling 36h news window, or inserts a placeholder
      when no summarizer is configured. Same Telegram delivery semantics.
    """

    def __init__(
        self,
        session: Session,
        *,
        summarizer: LLMSummarizer | None = None,
        news_fetcher: NewsApiFetcherService | None = None,
        keyword_extractor: KeywordExtractor | None = None,
        candidate_filter: PerUserCandidateFilter | None = None,
        telegram_sender: TelegramSender | None = None,
    ) -> None:
        self._session = session
        self._summarizer = summarizer
        self._news_fetcher = news_fetcher
        self._keyword_extractor = keyword_extractor
        self._candidate_filter = candidate_filter
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

    def append_placeholder_for_user(self, user_id: int, *, force_placeholder: bool = False) -> int:
        """User-triggered POST /summary/generate. Uses the real pipeline when configured.

        Does NOT fetch news (that's a bulk-job responsibility). Uses whatever news rows
        the daily job has most recently stored. Falls back to placeholder on LLM error
        or when no summarizer is configured. The resulting summary is also pushed to
        the user's Telegram chat when both a sender and a configured transport exist.

        `force_placeholder=True` skips the LLM entirely and inserts the deterministic
        placeholder row regardless of summarizer configuration (used by e2e/CI).
        """
        today_label = datetime.now(UTC).strftime("%Y-%m-%d")
        interests, scores, news, summaries, transports = self._components()
        if force_placeholder or self._summarizer is None:
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
        """Nightly job entry point: NewsAPI-based, demand-driven, previous-day digest per user."""
        now = datetime.now(UTC)
        y_start, y_end, date_label = _previous_day_window(now)

        users_repo = UserRepository(self._session)
        interests_repo = InterestRepository(self._session)
        scores_repo = ScoreRepository(self._session)
        news_repo = NewsRepository(self._session)
        summaries_repo = SummaryRepository(self._session)
        transports = TransportService(self._session)

        all_user_ids = users_repo.list_all_ids()
        users_with_interests = _users_with_interests(users_repo, interests_repo)
        skipped_no_interests = len(all_user_ids) - len(users_with_interests)

        stats: dict[str, int] = {
            "users_total": len(all_user_ids),
            "users_processed": 0,
            "skipped_no_interests": skipped_no_interests,
            "digest_failed": 0,
            "news_articles_fetched": 0,
            "keyword_extraction_failed": 0,
            "telegram_sent": 0,
            "telegram_skipped_no_config": 0,
            "telegram_failed": 0,
            "telegram_no_sender": 0,
        }

        if not users_with_interests:
            self._session.commit()
            return stats

        query: str | None = None
        if self._keyword_extractor is not None:
            query = self._keyword_extractor.extract(users_with_interests)
            if query is None:
                stats["keyword_extraction_failed"] = 1

        if query is not None and self._news_fetcher is not None:
            try:
                stats["news_articles_fetched"] = self._news_fetcher.fetch_and_store(
                    query=query,
                    start=y_start.replace(tzinfo=None),
                    end=y_end.replace(tzinfo=None),
                )
            except NewsFetchError as exc:
                logger.warning("NewsAPI fetch failed; continuing with stored articles: %s", exc)

        pool = news_repo.list_in_window(
            start=y_start.replace(tzinfo=None),
            end=y_end.replace(tzinfo=None),
            limit=settings.news_max_articles,
        )

        for user_id, interests_text in users_with_interests:
            if self._candidate_filter is not None and pool:
                filtered = self._candidate_filter.pick_top(
                    interests_text=interests_text,
                    articles=pool,
                    top_n=settings.per_user_digest_limit,
                )
            else:
                filtered = pool[: settings.per_user_digest_limit]

            recent_scores = scores_repo.list_recent_for_user(user_id, limit=RECENT_SCORES_LIMIT)
            prompt = build_summary_prompt(
                date_label=date_label,
                interests_text=interests_text,
                recent_scores=score_signals_from_rows(recent_scores),
                news=news_items_from_rows(filtered),
            )
            if self._summarizer is None:
                stats["digest_failed"] += 1
                continue
            try:
                body = self._summarizer.generate(prompt=prompt)
            except LLMError as exc:
                logger.warning("Digest LLM failed for user_id=%s: %s", user_id, exc)
                stats["digest_failed"] += 1
                continue

            summaries_repo.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
            outcome = _deliver_to_telegram(
                user_id=user_id,
                body=body,
                transports=transports,
                sender=self._telegram_sender,
            )
            stats[f"telegram_{outcome}"] += 1
            stats["users_processed"] += 1

        self._session.commit()
        return stats


__all__ = [
    "MockSummaryService",
    "PostgresSummaryService",
    "SummaryMaintenanceService",
    "SummaryService",
    "insert_generated_summary_for_user",
    "run_summary_generation_for_all_users",
]
