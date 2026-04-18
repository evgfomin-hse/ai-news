"""Insert `public.summaries` rows — nightly job and manual triggers call into here."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.summaries import SummaryRepository
from app.repositories.users import UserRepository

BODY_TEMPLATE = """## Daily summary — {date}

_Auto-generated._ Wire your own pipeline (LLM, News API, DB rollups) to replace this placeholder.
"""


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def insert_generated_summary_for_user(db: Session, user_id: int) -> int:
    """Appends one `summaries` row for `user_id`. Returns number of rows inserted (0 or 1)."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    SummaryRepository(db).append_row(
        user_id=user_id,
        summary=BODY_TEMPLATE.format(date=stamp),
        created_at=_now_naive_utc(),
    )
    return 1


def run_summary_generation_for_all_users(db: Session) -> dict[str, int]:
    """One new summary row per user (same logic as the nightly job)."""
    users = UserRepository(db)
    summaries = SummaryRepository(db)
    user_ids = users.list_all_ids()
    for uid in user_ids:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        summaries.append_row(
            user_id=uid,
            summary=BODY_TEMPLATE.format(date=stamp),
            created_at=_now_naive_utc(),
        )
    return {"users": len(user_ids), "rows_inserted": len(user_ids)}
