"""Unit tests for the NewsAPI fetcher. HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests
from sqlalchemy.orm import Session

from app.services.news_service import (
    NEWSAPI_SOURCE_TAG,
    NewsFetchError,
    NewsFetcherService,
)


@dataclass
class _Resp:
    payload: Any
    raise_exc: Exception | None = None

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _fake_get(response: _Resp):
    captured: dict[str, Any] = {}

    def _get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return response

    return _get, captured


def test_fetch_and_store_raises_when_api_key_missing(db: Session):
    svc = NewsFetcherService(db, api_key="", http_get=_fake_get(_Resp({}))[0])
    with pytest.raises(NewsFetchError, match="NEWS_API_KEY"):
        svc.fetch_and_store()


def test_fetch_and_store_raises_on_network_error(db: Session):
    def _raise(*_a, **_k):
        raise requests.RequestException("boom")

    svc = NewsFetcherService(db, api_key="k", http_get=_raise)
    with pytest.raises(NewsFetchError, match="Could not reach NewsAPI"):
        svc.fetch_and_store()


def test_fetch_and_store_raises_on_non_json(db: Session):
    get, _ = _fake_get(_Resp(ValueError("not json")))
    svc = NewsFetcherService(db, api_key="k", http_get=get)
    with pytest.raises(NewsFetchError, match="non-JSON"):
        svc.fetch_and_store()


def test_fetch_and_store_raises_when_payload_status_not_ok(db: Session):
    get, _ = _fake_get(_Resp({"status": "error", "message": "apiKeyInvalid"}))
    svc = NewsFetcherService(db, api_key="k", http_get=get)
    with pytest.raises(NewsFetchError, match="apiKeyInvalid"):
        svc.fetch_and_store()


def test_fetch_and_store_skips_malformed_articles(db: Session):
    get, _ = _fake_get(
        _Resp(
            {
                "status": "ok",
                "articles": [
                    {"title": "ok one", "description": "d", "url": "u"},
                    {"title": "", "description": "empty title"},  # skipped (empty title)
                    {"description": "no title key"},  # skipped (missing title)
                    "not a dict",  # skipped (not a dict)
                ],
            }
        )
    )
    svc = NewsFetcherService(db, api_key="k", http_get=get)
    inserted = svc.fetch_and_store()
    assert inserted == 1


def test_fetch_and_store_persists_articles_with_source_tag(db: Session):
    get, captured = _fake_get(
        _Resp(
            {
                "status": "ok",
                "articles": [
                    {
                        "title": "Title A",
                        "description": "Desc A",
                        "url": "https://a.example",
                        "publishedAt": "2026-05-23T10:15:00Z",
                    }
                ],
            }
        )
    )
    svc = NewsFetcherService(db, api_key="k", page_size=20, http_get=get)
    inserted = svc.fetch_and_store()
    assert inserted == 1
    assert captured["params"]["pageSize"] == 20
    assert captured["params"]["apiKey"] == "k"

    from app.models import NewsArticle

    rows = db.query(NewsArticle).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.title == "Title A"
    assert row.description == "Desc A"
    assert row.url == "https://a.example"
    assert row.source == NEWSAPI_SOURCE_TAG
    assert row.published_at is not None


def test_fetch_and_store_returns_zero_when_no_articles_field(db: Session):
    get, _ = _fake_get(_Resp({"status": "ok", "articles": "not a list"}))
    svc = NewsFetcherService(db, api_key="k", http_get=get)
    assert svc.fetch_and_store() == 0
