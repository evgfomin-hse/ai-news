"""Unit tests for NewsApiFetcherService — HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
import requests
from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.services.news_service import NewsApiFetcherService, NewsFetchError


@dataclass
class _Resp:
    payload: Any
    json_error: Exception | None = None

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


@dataclass
class _FakeHttp:
    responses: list[_Resp]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "params": dict(params or {}), "headers": dict(headers or {})}
        )
        if not self.responses:
            raise AssertionError("Unexpected extra HTTP call")
        return self.responses.pop(0)


def _ok(articles: list[dict[str, Any]], total: int | None = None) -> _Resp:
    return _Resp({"status": "ok", "totalResults": total if total is not None else len(articles),
                  "articles": articles})


def _article(title: str, url: str, published: str = "2026-06-07T10:15:00Z") -> dict[str, Any]:
    return {"title": title, "url": url, "description": "d", "publishedAt": published}


def _start_end() -> tuple[datetime, datetime]:
    return datetime(2026, 6, 7, 0, 0, 0), datetime(2026, 6, 7, 23, 59, 59)


def test_raises_when_api_key_missing(db: Session):
    svc = NewsApiFetcherService(db, api_key="", http_get=_FakeHttp([]))
    start, end = _start_end()
    with pytest.raises(NewsFetchError, match="NEWS_API_KEY"):
        svc.fetch_and_store(query="AI", start=start, end=end)


def test_raises_on_network_error(db: Session):
    def _raise(url, params=None, headers=None, timeout=None):
        raise requests.RequestException("boom")

    svc = NewsApiFetcherService(db, api_key="k", http_get=_raise)
    start, end = _start_end()
    with pytest.raises(NewsFetchError, match="Could not reach NewsAPI"):
        svc.fetch_and_store(query="AI", start=start, end=end)


def test_raises_on_non_json(db: Session):
    http = _FakeHttp([_Resp(payload=None, json_error=ValueError("bad json"))])
    svc = NewsApiFetcherService(db, api_key="k", http_get=http)
    start, end = _start_end()
    with pytest.raises(NewsFetchError, match="non-JSON"):
        svc.fetch_and_store(query="AI", start=start, end=end)


def test_raises_on_error_status_with_message(db: Session):
    http = _FakeHttp([_Resp({"status": "error", "code": "apiKeyInvalid", "message": "bad key"})])
    svc = NewsApiFetcherService(db, api_key="k", http_get=http)
    start, end = _start_end()
    with pytest.raises(NewsFetchError, match="bad key"):
        svc.fetch_and_store(query="AI", start=start, end=end)


def test_maximum_results_reached_is_not_fatal(db: Session):
    # Free-tier pagination cap on the first page → 0 stored, no exception.
    http = _FakeHttp(
        [_Resp({"status": "error", "code": "maximumResultsReached", "message": "cap"})]
    )
    svc = NewsApiFetcherService(db, api_key="k", http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 0


def test_builds_get_with_expected_params_and_header(db: Session):
    http = _FakeHttp([_ok([])])
    svc = NewsApiFetcherService(db, api_key="secret-key", language="en", page_size=100, http_get=http)
    start, end = _start_end()
    svc.fetch_and_store(query="(AI OR ML)", start=start, end=end)

    call = http.calls[0]
    assert call["url"] == "https://newsapi.org/v2/everything"
    assert call["headers"]["X-Api-Key"] == "secret-key"
    p = call["params"]
    assert p["q"] == "(AI OR ML)"
    assert p["language"] == "en"
    assert p["pageSize"] == 100
    assert p["sortBy"] == "publishedAt"
    assert p["from"] == "2026-06-07T00:00:00"
    assert p["to"] == "2026-06-07T23:59:59"


def test_parses_articles_and_persists_with_source_tag(db: Session):
    http = _FakeHttp(
        [_ok([_article("Title A", "https://a.example"), _article("Title B", "https://b.example")])]
    )
    svc = NewsApiFetcherService(db, api_key="k", page_size=100, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 2

    rows = db.query(NewsArticle).all()
    assert {r.title for r in rows} == {"Title A", "Title B"}
    assert {r.source for r in rows} == {"newsapi:everything"}
    assert all(r.published_at is not None for r in rows)


def test_dedupes_by_url(db: Session):
    http = _FakeHttp(
        [_ok([
            _article("A1", "https://dup.example"),
            _article("A2", "https://dup.example"),
            _article("B", "https://b.example"),
        ])]
    )
    svc = NewsApiFetcherService(db, api_key="k", page_size=100, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 2


def test_paginates_until_short_page(db: Session):
    page1 = [_article(f"A{i}", f"https://a{i}.example") for i in range(2)]
    page2 = [_article("B", "https://b.example")]  # short page → stop
    http = _FakeHttp([_ok(page1, total=10), _ok(page2, total=10)])
    svc = NewsApiFetcherService(db, api_key="k", page_size=2, max_articles=100, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 3
    assert [c["params"]["page"] for c in http.calls] == [1, 2]


def test_stops_at_max_articles(db: Session):
    page1 = [_article(f"A{i}", f"https://a{i}.example") for i in range(2)]
    http = _FakeHttp([_ok(page1, total=10)])
    svc = NewsApiFetcherService(db, api_key="k", page_size=2, max_articles=2, http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 2
    assert len(http.calls) == 1  # didn't fetch a second page


def test_returns_zero_when_no_articles_field(db: Session):
    http = _FakeHttp([_Resp({"status": "ok", "totalResults": 0})])
    svc = NewsApiFetcherService(db, api_key="k", http_get=http)
    start, end = _start_end()
    assert svc.fetch_and_store(query="AI", start=start, end=end) == 0
