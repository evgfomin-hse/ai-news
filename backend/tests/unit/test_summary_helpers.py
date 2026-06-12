"""Unit tests for the pure helpers added to summary_service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.summary_service import _previous_day_window, _users_with_interests


def test_previous_day_window_returns_two_days_ago_full_utc_day_and_iso_label():
    now = datetime(2026, 6, 6, 3, 0, 0, tzinfo=UTC)
    start, end, label = _previous_day_window(now)

    assert start == datetime(2026, 6, 4, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 6, 4, 23, 59, 59, tzinfo=UTC)
    assert label == "2026-06-04"


def test_previous_day_window_handles_first_of_month():
    now = datetime(2026, 7, 1, 3, 0, 0, tzinfo=UTC)
    start, end, label = _previous_day_window(now)
    assert start == datetime(2026, 6, 29, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 6, 29, 23, 59, 59, tzinfo=UTC)
    assert label == "2026-06-29"


@dataclass
class _Iface:
    text: str | None


class _FakeUsers:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids

    def list_all_ids(self) -> list[int]:
        return self.ids


class _FakeInterests:
    def __init__(self, mapping: dict[int, _Iface | None]) -> None:
        self.mapping = mapping

    def get_latest_for_user(self, user_id: int) -> _Iface | None:
        return self.mapping.get(user_id)


def test_users_with_interests_filters_users_with_no_row_or_empty_text():
    users = _FakeUsers([1, 2, 3, 4])
    interests = _FakeInterests(
        {
            1: _Iface(text="AI"),
            2: None,  # no row at all
            3: _Iface(text="   "),  # whitespace only
            4: _Iface(text=""),  # empty
        }
    )

    out = _users_with_interests(users, interests)

    assert out == [(1, "AI")]


def test_users_with_interests_preserves_user_order_from_list_all_ids():
    users = _FakeUsers([7, 3, 5])
    interests = _FakeInterests(
        {
            3: _Iface(text="ML"),
            5: _Iface(text="climate"),
            7: _Iface(text="AI"),
        }
    )

    out = _users_with_interests(users, interests)

    assert out == [(7, "AI"), (3, "ML"), (5, "climate")]
