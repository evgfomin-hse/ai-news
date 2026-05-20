"""User summaries: read from `public.summaries`, placeholder generation, and maintenance."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.repositories.summary_repository import SummaryRepository
from app.repositories.user_repository import UserRepository
from app.schemas.summary import SummaryItem, UserSummaryResponse


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


def _append_placeholder_row(summaries: SummaryRepository, user_id: int) -> None:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    summaries.append_row(
        user_id=user_id,
        summary=BODY_TEMPLATE.format(date=stamp),
        created_at=naive_utc_now(),
    )


def insert_generated_summary_for_user(db: Session, user_id: int) -> int:
    """Appends one `summaries` row for `user_id`. Returns number of rows inserted (0 or 1)."""
    _append_placeholder_row(SummaryRepository(db), user_id)
    return 1


def run_summary_generation_for_all_users(db: Session) -> dict[str, int]:
    """One new summary row per user (same logic as the nightly job)."""
    users = UserRepository(db)
    summaries = SummaryRepository(db)
    user_ids = users.list_all_ids()
    for uid in user_ids:
        _append_placeholder_row(summaries, uid)
    return {"users": len(user_ids), "rows_inserted": len(user_ids)}


class SummaryMaintenanceService:
    """Write-side summary operations (job + manual append), owns transaction commit."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append_placeholder_for_user(self, user_id: int) -> int:
        n = insert_generated_summary_for_user(self._session, user_id)
        self._session.commit()
        return n

    def run_bulk_for_all_users(self) -> dict[str, int]:
        stats = run_summary_generation_for_all_users(self._session)
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
