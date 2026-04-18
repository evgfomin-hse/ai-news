from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Summary
from app.services.summary.base import SummaryService
from app.services.summary.schemas import SummaryItem, UserSummaryResponse


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size


class PostgresSummaryService(SummaryService):
    """Loads markdown rows from coursework `public.summaries` with offset pagination."""

    EMPTY_NOTICE = """## No rows in `public.summaries`

There are no summary records for your user yet. Insert rows into **`summaries`** (`user_id`, `summary`, `created_at`) to see them here."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_summary_for_user(
        self,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> UserSummaryResponse:
        total = int(
            self._db.scalar(
                select(func.count()).select_from(Summary).where(Summary.user_id == user_id)
            )
            or 0
        )
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

        rows = list(
            self._db.scalars(
                select(Summary)
                .where(Summary.user_id == user_id)
                .order_by(Summary.created_at.desc().nulls_last(), Summary.id.desc())
                .offset(offset)
                .limit(page_size)
            ).all()
        )

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
