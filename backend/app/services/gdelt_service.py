"""GDELT DOC API v2 fetcher; persists results to `news_articles`."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.models import NewsArticle
from app.repositories.news_repository import NewsRepository

logger = logging.getLogger(__name__)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_SOURCE_TAG = "gdelt:doc"


class GdeltFetchError(RuntimeError):
    """Raised when GDELT cannot be reached or returns an unusable payload."""


def _format_gdelt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _parse_seendate(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    # GDELT seendate examples: "20260605T101500Z" or "20260605T101500".
    try:
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.strptime(s, "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def _article_from_payload(item: dict[str, Any], now: datetime) -> NewsArticle | None:
    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    url = item.get("url") if isinstance(item.get("url"), str) else None
    return NewsArticle(
        fetched_at=now,
        source=GDELT_SOURCE_TAG,
        title=title.strip(),
        description=None,  # GDELT doesn't provide article snippets.
        url=url,
        published_at=_parse_seendate(item.get("seendate")),
    )


class GdeltFetcherService:
    """Fetches yesterday's news from GDELT DOC API and stores it as `NewsArticle` rows.

    Pagination: GDELT DOC has no `page` param. We walk the time window by narrowing
    `enddatetime` to the oldest seen timestamp - 1s after each full page.
    """

    def __init__(
        self,
        session: Session,
        *,
        max_articles: int = 2000,
        max_records_per_request: int = 250,
        http_get=requests.get,
    ) -> None:
        self._session = session
        self._articles = NewsRepository(session)
        self._max_articles = max_articles
        self._max_records_per_request = max_records_per_request
        self._http_get = http_get

    def fetch_and_store(
        self,
        *,
        query: str,
        start: datetime,
        end: datetime,
    ) -> int:
        seen_urls: set[str] = set()
        accumulated: list[NewsArticle] = []
        now = naive_utc_now()
        current_end = end

        while len(accumulated) < self._max_articles:
            page = self._fetch_one(query=query, start=start, end=current_end)
            if not page:
                break

            new_in_page: list[NewsArticle] = []
            oldest_dt_in_page: datetime | None = None
            for raw in page:
                if not isinstance(raw, dict):
                    continue
                built = _article_from_payload(raw, now)
                if built is None or not built.url:
                    continue
                if built.url in seen_urls:
                    continue
                seen_urls.add(built.url)
                new_in_page.append(built)
                pa = built.published_at
                if pa is not None and (oldest_dt_in_page is None or pa < oldest_dt_in_page):
                    oldest_dt_in_page = pa

                if len(accumulated) + len(new_in_page) >= self._max_articles:
                    break

            accumulated.extend(new_in_page)

            # Stop conditions: short page (no more results) or cap reached.
            if len(page) < self._max_records_per_request:
                break
            if len(accumulated) >= self._max_articles:
                break

            # Narrow window for next request.
            if oldest_dt_in_page is None:
                break  # Can't paginate without dates.
            next_end = oldest_dt_in_page - timedelta(seconds=1)
            if next_end <= start:
                break
            current_end = next_end

        if not accumulated:
            return 0

        inserted = self._articles.insert_many(accumulated[: self._max_articles])
        self._session.commit()
        logger.info("GDELT: stored %d articles", inserted)
        return inserted

    def _fetch_one(self, *, query: str, start: datetime, end: datetime) -> list[Any]:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": self._max_records_per_request,
            "sort": "DateDesc",
            "sourcelang": "eng",
            "startdatetime": _format_gdelt_dt(start),
            "enddatetime": _format_gdelt_dt(end),
        }
        try:
            r = self._http_get(GDELT_DOC_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            logger.warning("GDELT request failed: %s", exc)
            raise GdeltFetchError("Could not reach GDELT") from exc

        if not getattr(r, "ok", True):
            raise GdeltFetchError(f"GDELT: HTTP {getattr(r, 'status_code', '?')}")

        try:
            payload = r.json()
        except ValueError as exc:
            raise GdeltFetchError("GDELT returned non-JSON") from exc

        articles = payload.get("articles") if isinstance(payload, dict) else None
        return articles if isinstance(articles, list) else []
