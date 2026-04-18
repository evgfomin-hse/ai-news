from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Interest


def naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_interest_row(db: Session, user_id: int) -> Interest | None:
    return db.scalar(
        select(Interest)
        .where(Interest.user_id == user_id)
        .order_by(Interest.id.desc())
        .limit(1)
    )
