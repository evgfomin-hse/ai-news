"""NewsAPI.org /everything fetcher; persists results to the `news_articles` table.

Same role and `fetch_and_store(query, start, end)` interface the pipeline previously
expected from GDELT: take the LLM keyword query + a date window, fetch matching
articles, and store them as `NewsArticle` rows.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.time import naive_utc_now
from app.models import NewsArticle
from app.repositories.news_repository import NewsRepository

logger = logging.getLogger(__name__)

NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
NEWSAPI_SOURCE_TAG = "newsapi:everything"


class NewsFetchError(RuntimeError):
    """Raised when NewsAPI cannot be reached or returns a non-ok payload."""


def _format_newsapi_dt(dt: datetime) -> str:
    """NewsAPI accepts ISO-8601; we pass naive-UTC datetimes without an offset."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _parse_published_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    # NewsAPI returns ISO-8601 strings like "2026-06-07T10:15:00Z".
    s = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None


def _article_from_payload(item: dict[str, Any], now: datetime) -> NewsArticle | None:
    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    description = item.get("description") if isinstance(item.get("description"), str) else None
    url = item.get("url") if isinstance(item.get("url"), str) else None
    return NewsArticle(
        fetched_at=now,
        source=NEWSAPI_SOURCE_TAG,
        title=title.strip(),
        description=description,
        url=url,
        published_at=_parse_published_at(item.get("publishedAt")),
    )


class NewsApiFetcherService:
    """Fetches articles from NewsAPI's /everything endpoint and stores them.

    Pagination uses NewsAPI's `page`/`pageSize` params. The free Developer plan caps
    results at 100 (`maximumResultsReached`), which we treat as "no more pages" rather
    than a hard error.
    """

    def __init__(
        self,
        session: Session,
        *,
        api_key: str,
        language: str = "en",
        page_size: int = 100,
        max_articles: int = 100,
        http_get=requests.get,
    ) -> None:
        self._session = session
        self._articles = NewsRepository(session)
        self._api_key = api_key
        self._language = language
        self._page_size = page_size
        self._max_articles = max_articles
        self._http_get = http_get

    def fetch_and_store(self, *, query: str, start: datetime, end: datetime) -> int:
        """Fetch articles matching `query` within [start, end]; persist and return the count."""
        if not self._api_key.strip():
            raise NewsFetchError("NEWS_API_KEY is not configured")

        seen_urls: set[str] = set()
        accumulated: list[NewsArticle] = []
        now = naive_utc_now()
        page = 1

        while len(accumulated) < self._max_articles:
            batch, total = self._fetch_page(query=query, start=start, end=end, page=page)
            if not batch:
                break

            for item in batch:
                if not isinstance(item, dict):
                    continue
                built = _article_from_payload(item, now)
                if built is None or not built.url or built.url in seen_urls:
                    continue
                seen_urls.add(built.url)
                accumulated.append(built)
                if len(accumulated) >= self._max_articles:
                    break

            if len(batch) < self._page_size:
                break  # last page
            if len(accumulated) >= min(total, self._max_articles):
                break
            page += 1

        if not accumulated:
            return 0

        inserted = self._articles.insert_many(accumulated[: self._max_articles])
        self._session.commit()
        logger.info("NewsAPI: stored %d articles", inserted)
        return inserted

    def _fetch_page(
        self, *, query: str, start: datetime, end: datetime, page: int
    ) -> tuple[list[Any], int]:
        params = {
            "q": query,
            "from": _format_newsapi_dt(start),
            "to": _format_newsapi_dt(end),
            "language": self._language,
            "sortBy": "publishedAt",
            "pageSize": self._page_size,
            "page": page,
        }
        try:
            r = self._http_get(
                NEWSAPI_EVERYTHING_URL,
                params=params,
                headers={"X-Api-Key": self._api_key},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("NewsAPI request failed: %s", exc)
            raise NewsFetchError("Could not reach NewsAPI") from exc

        try:
            payload = r.json()
        except ValueError as exc:
            raise NewsFetchError("NewsAPI returned a non-JSON response") from exc

        status = payload.get("status") if isinstance(payload, dict) else None
        if status != "ok":
            code = payload.get("code") if isinstance(payload, dict) else None
            message = (payload.get("message") if isinstance(payload, dict) else None) or "Unknown error"
            # Free-tier pagination cap: stop cleanly instead of failing the whole run.
            if code == "maximumResultsReached":
                logger.info("NewsAPI: hit result cap on page %d; stopping pagination", page)
                return [], 0
            raise NewsFetchError(f"NewsAPI: {message}")

        articles = payload.get("articles")
        total = payload.get("totalResults")
        if not isinstance(articles, list):
            return [], 0
        return articles, total if isinstance(total, int) else 0
