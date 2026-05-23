"""NewsAPI.org top-headlines fetcher; persists results to the `news_articles` table."""

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

NEWSAPI_TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"
NEWSAPI_SOURCE_TAG = "newsapi:top-headlines"


class NewsFetchError(RuntimeError):
    """Raised when NewsAPI cannot be reached or returns a non-ok payload."""


def _parse_published_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().replace("Z", "+00:00")
    try:
        # NewsAPI returns ISO-8601 strings like "2026-05-23T10:15:00Z".
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


class NewsFetcherService:
    """Fetches a batch of top headlines and stores them as `NewsArticle` rows."""

    def __init__(
        self,
        session: Session,
        *,
        api_key: str,
        language: str = "en",
        page_size: int = 20,
        http_get=requests.get,  # injectable for tests
    ) -> None:
        self._session = session
        self._articles = NewsRepository(session)
        self._api_key = api_key
        self._language = language
        self._page_size = page_size
        self._http_get = http_get

    def fetch_and_store(self) -> int:
        """Fetch top headlines and persist them. Returns the number of rows inserted."""
        if not self._api_key.strip():
            raise NewsFetchError("NEWS_API_KEY is not configured")

        try:
            r = self._http_get(
                NEWSAPI_TOP_HEADLINES_URL,
                params={
                    "language": self._language,
                    "pageSize": self._page_size,
                    "apiKey": self._api_key,
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("NewsAPI request failed: %s", exc)
            raise NewsFetchError("Could not reach NewsAPI") from exc

        try:
            payload = r.json()
        except ValueError as exc:
            raise NewsFetchError("NewsAPI returned a non-JSON response") from exc

        status = payload.get("status")
        if status != "ok":
            message = payload.get("message") or "Unknown error"
            raise NewsFetchError(f"NewsAPI: {message}")

        raw_articles = payload.get("articles")
        if not isinstance(raw_articles, list):
            return 0

        now = naive_utc_now()
        articles: list[NewsArticle] = []
        for item in raw_articles:
            if not isinstance(item, dict):
                continue
            built = _article_from_payload(item, now)
            if built is not None:
                articles.append(built)

        inserted = self._articles.insert_many(articles)
        self._session.commit()
        logger.info("NewsAPI: stored %d articles", inserted)
        return inserted
