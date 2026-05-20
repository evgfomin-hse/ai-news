from datetime import UTC, datetime


def naive_utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
