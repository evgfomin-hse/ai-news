"""Insert `public.summaries` rows — nightly job and manual triggers call into here."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Summary, User

BODY_TEMPLATE = """## Daily summary — {date}

_Auto-generated._ Wire your own pipeline (LLM, News API, DB rollups) to replace this placeholder.
"""


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def insert_generated_summary_for_user(db: Session, user_id: int) -> int:
    """Appends one `summaries` row for `user_id`. Returns number of rows inserted (0 or 1)."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    row = Summary(
        user_id=user_id,
        summary=BODY_TEMPLATE.format(date=stamp),
        created_at=_now_naive_utc(),
    )
    db.add(row)
    return 1


def run_summary_generation_for_all_users(db: Session) -> dict[str, int]:
    """One new summary row per user (same logic as the nightly job)."""
    user_ids = list(db.scalars(select(User.id)).all())
    for uid in user_ids:
        insert_generated_summary_for_user(db, int(uid))
    return {"users": len(user_ids), "rows_inserted": len(user_ids)}
