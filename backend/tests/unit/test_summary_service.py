"""Pure unit tests for PostgresSummaryService logic with a fake repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.summary_service import PostgresSummaryService


@dataclass
class _FakeRow:
    id: int
    summary: str | None
    created_at: datetime | None


class _FakeRepo:
    def __init__(self, rows: list[_FakeRow]) -> None:
        self._rows = rows
        self.list_calls: list[tuple[int, int, int]] = []

    def count_for_user(self, user_id: int) -> int:
        return len(self._rows)

    def list_page_for_user(
        self, user_id: int, *, offset: int, limit: int
    ) -> list[_FakeRow]:
        self.list_calls.append((user_id, offset, limit))
        return self._rows[offset : offset + limit]


def _row(rid: int, ts: datetime | None) -> _FakeRow:
    return _FakeRow(id=rid, summary=f"body {rid}", created_at=ts)


class TestEmptyState:
    def test_empty_repo_returns_notice_and_zero_total(self):
        svc = PostgresSummaryService(_FakeRepo([]))
        resp = svc.get_summary_for_user(user_id=1, page=1, page_size=10)
        assert resp.total == 0
        assert resp.total_pages == 0
        assert resp.items == []
        assert resp.generated_at is None
        assert resp.notice == PostgresSummaryService.EMPTY_NOTICE


class TestPagination:
    def test_clamps_page_above_total(self):
        repo = _FakeRepo([_row(i, None) for i in range(1, 6)])
        svc = PostgresSummaryService(repo)
        resp = svc.get_summary_for_user(user_id=1, page=99, page_size=2)
        # 5 rows / page_size=2 → 3 pages; page 99 must clamp to 3.
        assert resp.total_pages == 3
        assert resp.page == 3
        assert repo.list_calls[-1] == (1, 4, 2)

    def test_computes_total_pages_with_partial_last_page(self):
        repo = _FakeRepo([_row(i, None) for i in range(1, 8)])
        svc = PostgresSummaryService(repo)
        resp = svc.get_summary_for_user(user_id=1, page=1, page_size=3)
        assert resp.total == 7
        assert resp.total_pages == 3

    def test_passes_offset_for_requested_page(self):
        repo = _FakeRepo([_row(i, None) for i in range(1, 11)])
        svc = PostgresSummaryService(repo)
        svc.get_summary_for_user(user_id=42, page=2, page_size=4)
        assert repo.list_calls == [(42, 4, 4)]


class TestItemMapping:
    def test_title_falls_back_when_created_at_is_null(self):
        repo = _FakeRepo([_row(1, None)])
        resp = PostgresSummaryService(repo).get_summary_for_user(user_id=1)
        assert resp.items[0].title == "Summary"

    def test_title_uses_created_at_format(self):
        repo = _FakeRepo([_row(1, datetime(2024, 6, 1, 12, 30))])
        resp = PostgresSummaryService(repo).get_summary_for_user(user_id=1)
        assert resp.items[0].title == "2024-06-01 12:30"

    def test_generated_at_picks_max_created_at_and_is_utc(self):
        rows = [
            _row(1, datetime(2024, 1, 1, 0, 0)),
            _row(2, datetime(2024, 6, 1, 12, 0)),
            _row(3, datetime(2024, 3, 1, 0, 0)),
        ]
        resp = PostgresSummaryService(_FakeRepo(rows)).get_summary_for_user(user_id=1)
        assert resp.generated_at is not None
        assert resp.generated_at.tzinfo == UTC
        assert resp.generated_at.replace(tzinfo=None) == datetime(2024, 6, 1, 12, 0)
