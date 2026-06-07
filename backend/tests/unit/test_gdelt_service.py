"""Unit tests for GdeltFetcherService — HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
import requests
from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.services.gdelt_service import GdeltFetchError, GdeltFetcherService


@dataclass
class _Resp:
    payload: Any
    status_code: int = 200
    ok: bool = True
    json_error: Exception | None = None
    text: str | None = None

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


@dataclass
class _FakeHttp:
    responses: list[_Resp]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        if not self.responses:
            raise AssertionError("Unexpected extra HTTP call")
        return self.responses.pop(0)


class _Clock:
    """Deterministic monotonic clock + sleep; sleeping advances the clock."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


def _article(title: str, url: str, seendate: str) -> dict[str, Any]:
    return {"title": title, "url": url, "seendate": seendate, "domain": "example.com"}


def _start_end() -> tuple[datetime, datetime]:
    return datetime(2026, 6, 5, 0, 0, 0), datetime(2026, 6, 5, 23, 59, 59)


def test_raises_when_http_get_fails(db: Session):
    def _raise(url, params=None, timeout=None):
        raise requests.RequestException("boom")

    svc = GdeltFetcherService(db, http_get=_raise)
    start, end = _start_end()
    with pytest.raises(GdeltFetchError, match="Could not reach GDELT"):
        svc.fetch_and_store(query="(AI)", start=start, end=end)


def test_raises_on_non_json(db: Session):
    http = _FakeHttp(responses=[_Resp(payload=None, json_error=ValueError("bad json"))])
    svc = GdeltFetcherService(db, http_get=http)
    start, end = _start_end()
    with pytest.raises(GdeltFetchError, match="non-JSON"):
        svc.fetch_and_store(query="(AI)", start=start, end=end)


def test_raises_on_http_error_status(db: Session):
    http = _FakeHttp(responses=[_Resp(payload={"articles": []}, ok=False, status_code=500)])
    svc = GdeltFetcherService(db, http_get=http)
    start, end = _start_end()
    with pytest.raises(GdeltFetchError, match="HTTP 500"):
        svc.fetch_and_store(query="(AI)", start=start, end=end)


def test_builds_get_with_expected_params(db: Session):
    http = _FakeHttp(responses=[_Resp(payload={"articles": []})])
    svc = GdeltFetcherService(db, max_records_per_request=250, http_get=http)
    start, end = _start_end()
    svc.fetch_and_store(query="(AI OR ML)", start=start, end=end)

    call = http.calls[0]
    assert call["url"] == "https://api.gdeltproject.org/api/v2/doc/doc"
    p = call["params"]
    assert p["query"] == "(AI OR ML)"
    assert p["mode"] == "ArtList"
    assert p["format"] == "json"
    assert p["maxrecords"] == 250
    assert p["sort"] == "DateDesc"
    assert p["sourcelang"] == "eng"
    assert p["startdatetime"] == "20260605000000"
    assert p["enddatetime"] == "20260605235959"


def test_parses_articles_and_persists_with_source_tag(db: Session):
    http = _FakeHttp(
        responses=[
            _Resp(
                payload={
                    "articles": [
                        _article("Title A", "https://a.example", "20260605T101500Z"),
                        _article("Title B", "https://b.example", "20260605T112000Z"),
                    ]
                }
            )
        ]
    )
    svc = GdeltFetcherService(db, max_records_per_request=250, http_get=http)
    start, end = _start_end()
    inserted = svc.fetch_and_store(query="(AI)", start=start, end=end)
    assert inserted == 2

    rows = db.query(NewsArticle).all()
    assert {r.title for r in rows} == {"Title A", "Title B"}
    assert {r.source for r in rows} == {"gdelt:doc"}
    assert all(r.description is None for r in rows)
    assert all(r.published_at is not None for r in rows)


def test_dedupes_by_url_within_a_single_call(db: Session):
    http = _FakeHttp(
        responses=[
            _Resp(
                payload={
                    "articles": [
                        _article("A1", "https://dup.example", "20260605T101500Z"),
                        _article("A2", "https://dup.example", "20260605T112000Z"),
                        _article("B", "https://b.example", "20260605T120000Z"),
                    ]
                }
            )
        ]
    )
    svc = GdeltFetcherService(db, max_records_per_request=250, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="(AI)", start=start, end=end) == 2


def test_paginates_by_narrowing_enddatetime_to_oldest_seen_minus_one_second(db: Session):
    # First page is "full" (==maxrecords) → triggers pagination.
    # Oldest seen on page 1 is 09:00:00 → next enddatetime = 08:59:59.
    page1 = [_article(f"A{i}", f"https://a{i}.example", "20260605T100000Z") for i in range(1, 3)]
    page1[-1]["seendate"] = "20260605T090000Z"  # oldest on page 1
    page2 = [_article("B", "https://b.example", "20260605T080000Z")]  # short page → stops loop
    http = _FakeHttp(
        responses=[_Resp(payload={"articles": page1}), _Resp(payload={"articles": page2})]
    )

    clock = _Clock()
    svc = GdeltFetcherService(
        db, max_records_per_request=2, http_get=http, sleep=clock.sleep, monotonic=clock.monotonic
    )
    start, end = _start_end()
    inserted = svc.fetch_and_store(query="(AI)", start=start, end=end)

    assert inserted == 3
    assert len(http.calls) == 2
    assert http.calls[1]["params"]["enddatetime"] == "20260605085959"


def test_throttles_at_least_min_interval_between_requests(db: Session):
    page1 = [_article(f"A{i}", f"https://a{i}.example", "20260605T100000Z") for i in range(1, 3)]
    page1[-1]["seendate"] = "20260605T090000Z"
    page2 = [_article("B", "https://b.example", "20260605T080000Z")]
    http = _FakeHttp(
        responses=[_Resp(payload={"articles": page1}), _Resp(payload={"articles": page2})]
    )
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        max_records_per_request=2,
        min_request_interval_seconds=5.0,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    svc.fetch_and_store(query="(AI)", start=start, end=end)

    # First request: no wait. Second request: throttled by the full interval.
    assert clock.sleeps == [5.0]


def test_retries_on_429_then_succeeds(db: Session):
    http = _FakeHttp(
        responses=[
            _Resp(payload="rate limited", ok=False, status_code=429),
            _Resp(payload={"articles": [_article("A", "https://a.example", "20260605T100000Z")]}),
        ]
    )
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        min_request_interval_seconds=5.0,
        max_retries=3,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    assert svc.fetch_and_store(query="(AI)", start=start, end=end) == 1
    assert len(http.calls) == 2  # one retry
    assert clock.sleeps  # backed off before retrying


def test_raises_after_exhausting_429_retries(db: Session):
    http = _FakeHttp(responses=[_Resp(payload="x", ok=False, status_code=429) for _ in range(4)])
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        min_request_interval_seconds=5.0,
        max_retries=3,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    with pytest.raises(GdeltFetchError, match="rate-limited"):
        svc.fetch_and_store(query="(AI)", start=start, end=end)
    assert len(http.calls) == 4  # initial + 3 retries


def test_retries_on_plaintext_rate_limit_returned_with_200(db: Session):
    # GDELT often returns its throttle notice as plain text with HTTP 200 (not 429).
    rate_limited = _Resp(
        payload=None,
        status_code=200,
        ok=True,
        json_error=ValueError("not json"),
        text="Please limit requests to one every 5 seconds or contact ...",
    )
    http = _FakeHttp(
        responses=[
            rate_limited,
            _Resp(payload={"articles": [_article("A", "https://a.example", "20260605T100000Z")]}),
        ]
    )
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        min_request_interval_seconds=5.0,
        max_retries=3,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    assert svc.fetch_and_store(query="(AI)", start=start, end=end) == 1
    assert len(http.calls) == 2  # treated the 200+plaintext as rate-limited and retried
    assert clock.sleeps  # backed off


def test_backoff_is_exponential_across_retries(db: Session):
    http = _FakeHttp(responses=[_Resp(payload="x", ok=False, status_code=429) for _ in range(4)])
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        min_request_interval_seconds=5.0,
        max_retries=3,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    with pytest.raises(GdeltFetchError, match="rate-limited"):
        svc.fetch_and_store(query="(AI)", start=start, end=end)
    # 5, 10, 20 — doubles each retry so it can outlast a short cooldown.
    assert clock.sleeps == [5.0, 10.0, 20.0]


def test_honors_retry_after_header_on_429(db: Session):
    resp_429 = _Resp(payload="x", ok=False, status_code=429)
    resp_429.headers = {"Retry-After": "12"}
    http = _FakeHttp(
        responses=[
            resp_429,
            _Resp(payload={"articles": [_article("A", "https://a.example", "20260605T100000Z")]}),
        ]
    )
    clock = _Clock()
    svc = GdeltFetcherService(
        db,
        min_request_interval_seconds=5.0,
        max_retries=3,
        http_get=http,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    start, end = _start_end()
    svc.fetch_and_store(query="(AI)", start=start, end=end)
    assert 12.0 in clock.sleeps  # waited the server-requested delay


def test_stops_when_max_articles_reached(db: Session):
    page1 = [_article(f"A{i}", f"https://a{i}.example", "20260605T100000Z") for i in range(1, 3)]
    page1[-1]["seendate"] = "20260605T090000Z"
    http = _FakeHttp(responses=[_Resp(payload={"articles": page1})])
    svc = GdeltFetcherService(db, max_articles=2, max_records_per_request=2, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="(AI)", start=start, end=end) == 2
    assert len(http.calls) == 1  # didn't paginate further


def test_returns_zero_when_response_has_no_articles_field(db: Session):
    http = _FakeHttp(responses=[_Resp(payload={"unrelated": []})])
    svc = GdeltFetcherService(db, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="(AI)", start=start, end=end) == 0
