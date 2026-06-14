from datetime import UTC, datetime

from app.core.time import naive_utc_now


def test_naive_utc_now_returns_naive_datetime():
    now = naive_utc_now()
    assert now.tzinfo is None


def test_naive_utc_now_is_close_to_utc_wall_clock():
    expected = datetime.now(UTC).replace(tzinfo=None)
    delta = abs((naive_utc_now() - expected).total_seconds())
    assert delta < 5
