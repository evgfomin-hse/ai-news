# Daily News Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current nightly NewsAPI top-headlines pipeline with a 03:00-UTC GDELT-based, demand-driven previous-day digest job that filters news per user via the LLM.

**Architecture:** A daily scheduler tick at 03:00 UTC runs four stages: (1) one LLM call extracts a global keyword query from the union of all users' interests; (2) `GdeltFetcherService` paginates GDELT DOC API over yesterday's UTC window, storing rows in `news_articles`; (3) for each user with non-empty interests, `PerUserCandidateFilter` makes chunked LLM calls (~500 titles per batch) to pick the top ~50; (4) the existing `build_summary_prompt` + `LLMSummarizer` writes the digest and the existing Telegram path delivers it. Users without interests, or whose digest LLM call fails, are skipped entirely — no placeholder rows.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, APScheduler, pytest, `requests` (HTTP), OpenRouter (OpenAI-compatible chat-completions), GDELT DOC API v2.

**Spec:** `docs/superpowers/specs/2026-06-06-daily-news-pipeline-design.md`.

**Commit policy:** This repo has a "no auto-commit" rule (user commits manually). The plan groups changes into logical commit-sized tasks; do **not** run `git commit` from inside tasks. After finishing a task, stop and let the user inspect + commit. Each task ends with "Stop here for user review/commit."

**Test runner:** `cd backend && .venv/bin/python -m pytest <path>` (matches `README.md`). All assertions below assume the virtualenv at `backend/.venv` is active.

---

## Task 1: Add new Settings fields (additive — keeps old ones for now)

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_config.py`

The new fields are needed by later tasks. Old NewsAPI fields stay until Task 8 deletes the fetcher.

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/unit/test_config.py`:

```python
def test_new_pipeline_settings_have_documented_defaults():
    s = Settings(**_kwargs())
    assert s.summary_schedule_hour == 3
    assert s.gdelt_max_articles == 2000
    assert s.gdelt_request_max_records == 250
    assert s.per_user_filter_batch == 500
    assert s.per_user_filter_top_per_batch == 25
    assert s.per_user_digest_limit == 50
    assert s.keyword_extractor_max_query_chars == 450


def test_summary_schedule_hour_clamps_in_valid_range_via_validator():
    # Pydantic accepts 0..23; out of range raises ValidationError.
    with pytest.raises(ValidationError):
        Settings(**_kwargs(summary_schedule_hour=24))
    with pytest.raises(ValidationError):
        Settings(**_kwargs(summary_schedule_hour=-1))
```

- [ ] **Step 2: Run and verify tests fail**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_config.py -v
```

Expected: both new tests FAIL with `AttributeError` (fields don't exist yet) / `ValidationError not raised`.

- [ ] **Step 3: Add the fields to `Settings`**

In `backend/app/core/config.py`, inside the `Settings` class, after the existing `news_fetch_limit` line, add:

```python
    # GDELT-based daily news pipeline (replaces NewsAPI top-headlines for the bulk job).
    summary_schedule_hour: int = Field(default=3, ge=0, le=23)
    gdelt_max_articles: int = 2000
    gdelt_request_max_records: int = 250
    per_user_filter_batch: int = 500
    per_user_filter_top_per_batch: int = 25
    per_user_digest_limit: int = 50
    keyword_extractor_max_query_chars: int = 450
```

And add to the imports at the top of the file:

```python
from pydantic import Field
```

(The existing `model_validator` import already pulls from `pydantic`; add `Field` to that import line instead if you prefer one combined import.)

- [ ] **Step 4: Run tests; verify they pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_config.py -v
```

Expected: all pass, including new ones.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 2: Add `NewsRepository.list_in_window`

**Files:**
- Modify: `backend/app/repositories/news_repository.py`
- Test: `backend/tests/integration/test_news_repository_list_in_window.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_news_repository_list_in_window.py`:

```python
"""Integration tests for NewsRepository.list_in_window — window selection on real SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.repositories.news_repository import NewsRepository


def _ts(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, 0, 0)


def _make(
    db: Session,
    *,
    title: str,
    fetched_at: datetime,
    published_at: datetime | None,
    url: str | None = None,
) -> NewsArticle:
    row = NewsArticle(
        fetched_at=fetched_at,
        source="gdelt:doc",
        title=title,
        description=None,
        url=url or f"https://example.test/{title}",
        published_at=published_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_returns_rows_with_published_at_inside_window(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    inside = _make(db, title="A", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 5, 14))
    before = _make(db, title="B", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 4, 23))
    after = _make(db, title="C", fetched_at=_ts(2026, 6, 6, 3), published_at=_ts(2026, 6, 6, 1))

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=10)

    ids = {r.id for r in rows}
    assert inside.id in ids
    assert before.id not in ids
    assert after.id not in ids


def test_falls_back_to_fetched_at_when_published_at_is_null(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    matching = _make(db, title="A", fetched_at=_ts(2026, 6, 5, 12), published_at=None)
    not_matching = _make(db, title="B", fetched_at=_ts(2026, 6, 4, 12), published_at=None)

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=10)

    ids = {r.id for r in rows}
    assert matching.id in ids
    assert not_matching.id not in ids


def test_respects_limit(db: Session):
    start, end = _ts(2026, 6, 5, 0), _ts(2026, 6, 5, 23) + timedelta(minutes=59, seconds=59)
    for i in range(5):
        _make(
            db,
            title=f"r{i}",
            fetched_at=_ts(2026, 6, 6, 3),
            published_at=_ts(2026, 6, 5, 10 + i),
        )

    rows = NewsRepository(db).list_in_window(start=start, end=end, limit=2)

    assert len(rows) == 2
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_news_repository_list_in_window.py -v
```

Expected: FAIL with `AttributeError: ... has no attribute 'list_in_window'`.

- [ ] **Step 3: Implement `list_in_window`**

Add to `backend/app/repositories/news_repository.py`:

```python
    def list_in_window(self, *, start: datetime, end: datetime, limit: int) -> list[NewsArticle]:
        """Articles in [start, end] by published_at, falling back to fetched_at when NULL.

        Ordered fetched_at desc, id desc so the caller sees most-recent rows first.
        """
        from sqlalchemy import func, or_, and_

        effective = func.coalesce(NewsArticle.published_at, NewsArticle.fetched_at)
        return list(
            self._session.scalars(
                select(NewsArticle)
                .where(and_(effective >= start, effective <= end))
                .order_by(NewsArticle.fetched_at.desc(), NewsArticle.id.desc())
                .limit(limit)
            ).all()
        )
```

Update the imports at the top of the file: ensure `from sqlalchemy import select` already exists (it does). The `func`, `or_`, `and_` imports are inline to avoid polluting the module's top level for this single helper.

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_news_repository_list_in_window.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full repo test suite to confirm nothing else broke**

```bash
cd backend && .venv/bin/python -m pytest tests/integration -v
```

Expected: all pass.

- [ ] **Step 6: Stop here for user review/commit.**

---

## Task 3: Build `KeywordExtractor` (TDD)

**Files:**
- Create: `backend/app/services/keyword_extractor.py`
- Test: `backend/tests/unit/test_keyword_extractor.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_keyword_extractor.py`:

```python
"""Unit tests for KeywordExtractor — LLM is replaced with an injected fake."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.services.keyword_extractor import KeywordExtractor
from app.services.llm_service import LLMError


@dataclass
class _FakeSummarizer:
    response: str | Exception

    def generate(self, *, prompt: str) -> str:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_returns_none_when_no_users():
    ext = KeywordExtractor(_FakeSummarizer(response="never called"))
    assert ext.extract([]) is None


def test_returns_none_when_all_interests_empty():
    ext = KeywordExtractor(_FakeSummarizer(response="never called"))
    assert ext.extract([(1, ""), (2, "   "), (3, "\n")]) is None


def test_returns_query_string_from_valid_json():
    payload = json.dumps({"global_query_keywords": ["AI", "robotics", "climate"]})
    ext = KeywordExtractor(_FakeSummarizer(response=payload))
    assert ext.extract([(1, "AI, robotics"), (2, "climate change")]) == "(AI OR robotics OR climate)"


def test_dedupes_case_insensitively_preserving_first_occurrence():
    payload = json.dumps({"global_query_keywords": ["AI", "ai", "Robotics", "ROBOTICS"]})
    ext = KeywordExtractor(_FakeSummarizer(response=payload))
    assert ext.extract([(1, "tech")]) == "(AI OR Robotics)"


def test_returns_none_on_llm_error():
    ext = KeywordExtractor(_FakeSummarizer(response=LLMError("boom")))
    assert ext.extract([(1, "AI")]) is None


def test_returns_none_on_malformed_json():
    ext = KeywordExtractor(_FakeSummarizer(response="not json"))
    assert ext.extract([(1, "AI")]) is None


def test_returns_none_when_keyword_list_missing_or_empty():
    ext = KeywordExtractor(_FakeSummarizer(response=json.dumps({})))
    assert ext.extract([(1, "AI")]) is None

    ext2 = KeywordExtractor(_FakeSummarizer(response=json.dumps({"global_query_keywords": []})))
    assert ext2.extract([(1, "AI")]) is None


def test_truncates_at_max_query_chars():
    keywords = [f"kw{i}" for i in range(200)]  # plenty to overflow
    payload = json.dumps({"global_query_keywords": keywords})
    ext = KeywordExtractor(_FakeSummarizer(response=payload), max_query_chars=30)
    query = ext.extract([(1, "tech")])
    assert query is not None
    assert len(query) <= 30
    assert query.startswith("(")
    assert query.endswith(")")
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_keyword_extractor.py -v
```

Expected: FAIL with `ModuleNotFoundError: app.services.keyword_extractor`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/keyword_extractor.py`:

```python
"""Extracts a GDELT-ready keyword query from the union of all users' interests."""

from __future__ import annotations

import json
import logging

from app.services.llm_service import LLMError, LLMSummarizer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are extracting search keywords for a news API query.

Input: a list of free-text "interests" strings from different users.
Task: produce a single deduplicated keyword/short-phrase list that, when joined
with " OR ", will surface news articles any of these users would care about.

Rules:
- Output ONLY a JSON object: {"global_query_keywords": ["kw1", "kw2", ...]}.
- Up to 25 entries. Prefer single nouns or 2-word phrases.
- Avoid stopwords, articles, generic terms ("news", "stuff").
- Use English keywords (the corpus is sourcelang=eng).
"""


class KeywordExtractor:
    """One LLM call → GDELT query string '(kw1 OR kw2 OR ...)'."""

    def __init__(
        self,
        summarizer: LLMSummarizer,
        *,
        max_query_chars: int = 450,
    ) -> None:
        self._summarizer = summarizer
        self._max_query_chars = max_query_chars

    def extract(self, users_with_interests: list[tuple[int, str]]) -> str | None:
        non_empty = [(uid, txt.strip()) for uid, txt in users_with_interests if txt and txt.strip()]
        if not non_empty:
            return None

        prompt = self._build_prompt(non_empty)
        try:
            raw = self._summarizer.generate(prompt=prompt)
        except LLMError as exc:
            logger.warning("Keyword extraction LLM failed: %s", exc)
            return None

        keywords = self._parse(raw)
        if not keywords:
            return None

        return self._format_query(keywords)

    @staticmethod
    def _build_prompt(non_empty: list[tuple[int, str]]) -> str:
        bullets = "\n".join(f"- user_{uid}: {txt}" for uid, txt in non_empty)
        return f"{_SYSTEM_PROMPT}\n\nInterests:\n{bullets}\n\nReturn the JSON object now."

    @staticmethod
    def _parse(raw: str) -> list[str]:
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Keyword extraction returned non-JSON: %r", raw[:200])
            return []
        if not isinstance(payload, dict):
            return []
        kws = payload.get("global_query_keywords")
        if not isinstance(kws, list):
            return []
        return [str(k).strip() for k in kws if isinstance(k, (str, int)) and str(k).strip()]

    def _format_query(self, keywords: list[str]) -> str:
        seen_lower: set[str] = set()
        deduped: list[str] = []
        for kw in keywords:
            lk = kw.lower()
            if lk in seen_lower:
                continue
            seen_lower.add(lk)
            deduped.append(kw)

        # Build incrementally; stop adding once we would exceed max_query_chars
        # (account for parens and " OR " joiners).
        accepted: list[str] = []
        for kw in deduped:
            candidate = "(" + " OR ".join([*accepted, kw]) + ")"
            if len(candidate) > self._max_query_chars:
                break
            accepted.append(kw)
        if not accepted:
            # Even one keyword overflowed — fall back to the single first keyword truncated.
            first = deduped[0][: max(self._max_query_chars - 2, 1)]
            return f"({first})"
        return "(" + " OR ".join(accepted) + ")"
```

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_keyword_extractor.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 4: Build `GdeltFetcherService` (TDD)

**Files:**
- Create: `backend/app/services/gdelt_service.py`
- Test: `backend/tests/unit/test_gdelt_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_gdelt_service.py`:

```python
"""Unit tests for GdeltFetcherService — HTTP is replaced with an injected fake."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
import requests
from sqlalchemy.orm import Session

from app.models import NewsArticle
from app.services.gdelt_service import GdeltFetcherService, GdeltFetchError


@dataclass
class _Resp:
    payload: Any
    status_code: int = 200
    ok: bool = True
    json_error: Exception | None = None

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

    svc = GdeltFetcherService(db, max_records_per_request=2, http_get=http)
    start, end = _start_end()
    inserted = svc.fetch_and_store(query="(AI)", start=start, end=end)

    assert inserted == 3
    assert len(http.calls) == 2
    assert http.calls[1]["params"]["enddatetime"] == "20260605085959"


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
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_gdelt_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/gdelt_service.py`:

```python
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

        try:
            payload = r.json()
        except ValueError as exc:
            raise GdeltFetchError("GDELT returned non-JSON") from exc

        if not getattr(r, "ok", True):
            raise GdeltFetchError(f"GDELT: HTTP {getattr(r, 'status_code', '?')}")

        articles = payload.get("articles") if isinstance(payload, dict) else None
        return articles if isinstance(articles, list) else []
```

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_gdelt_service.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 5: Build `PerUserCandidateFilter` (TDD)

**Files:**
- Create: `backend/app/services/candidate_filter.py`
- Test: `backend/tests/unit/test_candidate_filter.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_candidate_filter.py`:

```python
"""Unit tests for PerUserCandidateFilter — LLM replaced with a programmable fake."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from app.models import NewsArticle
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.llm_service import LLMError


@dataclass
class _ScriptedSummarizer:
    """Returns the next scripted response for each `generate` call."""

    responses: list[str | Exception]
    prompts: list[str] = field(default_factory=list)

    def generate(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("Unexpected extra LLM call")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _article(idx: int) -> NewsArticle:
    return NewsArticle(
        fetched_at=datetime(2026, 6, 6, 3, 0, 0),
        source="gdelt:doc",
        title=f"Title {idx}",
        description=None,
        url=f"https://example.test/a{idx}",
        published_at=datetime(2026, 6, 5, 12, 0, 0),
    )


def _picks(indices: list[int]) -> str:
    return json.dumps({"indices": indices})


def test_empty_input_returns_empty_no_llm_call():
    summ = _ScriptedSummarizer(responses=[])
    f = PerUserCandidateFilter(summ)
    assert f.pick_top(interests_text="AI", articles=[], top_n=50) == []
    assert summ.prompts == []


def test_chunks_at_batch_size_and_dedupes_across_batches():
    # 600 articles → batches of 500 + 100.
    pool = [_article(i) for i in range(600)]
    # Each batch returns indices 0..24 (top 25 per batch).
    summ = _ScriptedSummarizer(responses=[_picks(list(range(25))), _picks(list(range(25)))])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)

    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)

    # Batch 1 → articles 0..24; batch 2 → articles 500..524. Total 50, no dup.
    urls = [a.url for a in picked]
    assert len(picked) == 50
    assert len(set(urls)) == 50
    assert urls[:25] == [pool[i].url for i in range(25)]
    assert urls[25:] == [pool[500 + i].url for i in range(25)]


def test_returns_first_top_n_preserving_pool_order_when_more_picked():
    # 300 articles, batch_size 500 → single batch. LLM returns 30 indices, we want top 20.
    pool = [_article(i) for i in range(300)]
    summ = _ScriptedSummarizer(responses=[_picks(list(range(30)))])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=30)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=20)
    assert [a.url for a in picked] == [pool[i].url for i in range(20)]


def test_one_failed_batch_does_not_drop_other_batches():
    pool = [_article(i) for i in range(800)]
    # Batch 1 fails; batches 2 returns picks.
    summ = _ScriptedSummarizer(responses=[LLMError("boom"), _picks([0, 1, 2])])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)
    # Only batch 2's picks survive (indices 0..2 inside batch 2 = pool[500..502]).
    assert [a.url for a in picked] == [pool[500 + i].url for i in range(3)]


def test_all_batches_failing_falls_back_to_first_top_n():
    pool = [_article(i) for i in range(800)]
    summ = _ScriptedSummarizer(responses=[LLMError("boom"), LLMError("boom2")])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=10)
    assert [a.url for a in picked] == [pool[i].url for i in range(10)]


def test_malformed_json_treated_as_batch_failure():
    pool = [_article(i) for i in range(200)]
    summ = _ScriptedSummarizer(responses=["not json"])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    # Single batch, fails → fallback to first 5.
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=5)
    assert [a.url for a in picked] == [pool[i].url for i in range(5)]


def test_out_of_range_and_non_integer_indices_are_dropped():
    pool = [_article(i) for i in range(10)]
    summ = _ScriptedSummarizer(responses=[json.dumps({"indices": [0, 999, "x", -1, 3]})])
    f = PerUserCandidateFilter(summ, batch_size=500, top_per_batch=25)
    picked = f.pick_top(interests_text="AI", articles=pool, top_n=50)
    assert [a.url for a in picked] == [pool[0].url, pool[3].url]
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_candidate_filter.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the module**

Create `backend/app/services/candidate_filter.py`:

```python
"""Per-user candidate filtering — chunked LLM calls to narrow a big day's pool to top-N."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from app.models import NewsArticle
from app.services.llm_service import LLMError, LLMSummarizer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You select news articles relevant to a user's interests.

Input: the user's free-text interests, followed by a numbered list of article titles.
Task: return the indices of the most relevant articles, most relevant first.

Rules:
- Output ONLY a JSON object: {"indices": [int, int, ...]}.
- At most K indices (K is specified in the request).
- Indices refer to positions in the provided list (0-based).
- If nothing is relevant, return {"indices": []}.
"""


class PerUserCandidateFilter:
    """For each user, narrow the day's pool of articles to `top_n` LLM-ranked picks."""

    def __init__(
        self,
        summarizer: LLMSummarizer,
        *,
        batch_size: int = 500,
        top_per_batch: int = 25,
    ) -> None:
        self._summarizer = summarizer
        self._batch_size = batch_size
        self._top_per_batch = top_per_batch

    def pick_top(
        self,
        *,
        interests_text: str,
        articles: list[NewsArticle],
        top_n: int,
    ) -> list[NewsArticle]:
        if not articles:
            return []

        picked: list[NewsArticle] = []
        seen_urls: set[str] = set()
        any_batch_succeeded = False

        for offset, batch in self._iter_batches(articles):
            indices = self._ask_llm_for_indices(
                interests_text=interests_text,
                batch=batch,
                limit=self._top_per_batch,
            )
            if indices is None:
                continue  # Batch failed → contributes nothing.
            any_batch_succeeded = True
            for local_idx in indices:
                if local_idx < 0 or local_idx >= len(batch):
                    continue
                article = batch[local_idx]
                if not article.url or article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                picked.append(article)
                if len(picked) >= top_n:
                    return picked

        if not any_batch_succeeded:
            return articles[:top_n]

        return picked[:top_n]

    def _iter_batches(
        self, articles: list[NewsArticle]
    ) -> Iterable[tuple[int, list[NewsArticle]]]:
        for offset in range(0, len(articles), self._batch_size):
            yield offset, articles[offset : offset + self._batch_size]

    def _ask_llm_for_indices(
        self,
        *,
        interests_text: str,
        batch: list[NewsArticle],
        limit: int,
    ) -> list[int] | None:
        lines = "\n".join(f"{i}. {a.title}" for i, a in enumerate(batch))
        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"User interests:\n{interests_text}\n\n"
            f"Articles (K = {limit}):\n{lines}\n\n"
            "Return the JSON object now."
        )
        try:
            raw = self._summarizer.generate(prompt=prompt)
        except LLMError as exc:
            logger.warning("Candidate filter LLM failed: %s", exc)
            return None

        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("Candidate filter returned non-JSON: %r", raw[:200])
            return None

        if not isinstance(payload, dict):
            return None
        indices_raw = payload.get("indices")
        if not isinstance(indices_raw, list):
            return None

        result: list[int] = []
        for item in indices_raw:
            if isinstance(item, bool):
                continue  # bools are ints in Python; reject.
            if isinstance(item, int):
                result.append(item)
        return result[:limit]
```

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_candidate_filter.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 6: Rename `today_label` → `date_label` and stop rendering description

**Files:**
- Modify: `backend/app/services/summary_prompt.py`
- Modify: `backend/app/services/summary_service.py` (call sites)
- Modify: `backend/tests/unit/test_summary_prompt.py`

This rename touches two call sites in `summary_service.py` (`_generate_one_for_user` and any other use). All happen together — Python will raise `TypeError` if any caller is missed.

- [ ] **Step 1: Update tests to assert new behavior**

Replace the entire content of `backend/tests/unit/test_summary_prompt.py` with:

```python
"""Unit tests for the pure prompt builder."""

from __future__ import annotations

from app.services.summary_prompt import (
    NewsItem,
    ScoreSignal,
    build_summary_prompt,
)


def test_prompt_includes_date_label_in_rules_and_body():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="ML, hiking",
        recent_scores=[],
        news=[NewsItem(title="A", description=None, url=None)],
    )
    assert "Today's date: 2026-06-05" in prompt


def test_prompt_renders_interests_when_present():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="  Machine learning, cinema  ",
        recent_scores=[],
        news=[],
    )
    assert "User interests (free-text" in prompt
    assert "Machine learning, cinema" in prompt


def test_prompt_marks_interests_as_not_set_when_empty():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="",
        recent_scores=[],
        news=[],
    )
    assert "(not set; pick a balanced cross-section)" in prompt


def test_prompt_lists_recent_feedback_tagged_with_liked_or_disliked():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="",
        recent_scores=[
            ScoreSignal(value=True, description="loved the LLM coverage"),
            ScoreSignal(value=False, description=None),
        ],
        news=[],
    )
    assert "LIKED: loved the LLM coverage" in prompt
    assert "DISLIKED" in prompt


def test_prompt_marks_feedback_as_none_when_empty():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="ML",
        recent_scores=[],
        news=[],
    )
    assert "Recent feedback: (none yet)" in prompt


def test_prompt_renders_news_with_title_and_url_only_ignoring_description():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="",
        recent_scores=[],
        news=[
            NewsItem(title="Headline A", description="desc A IGNORED", url="https://a.example"),
            NewsItem(title="Headline B", description=None, url=None),
        ],
    )
    assert "desc A IGNORED" not in prompt
    assert "- Headline A [https://a.example]" in prompt
    assert "- Headline B" in prompt


def test_prompt_marks_news_as_none_when_empty():
    prompt = build_summary_prompt(
        date_label="2026-06-05",
        interests_text="ML",
        recent_scores=[],
        news=[],
    )
    assert "Today's news: (none)" in prompt
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_summary_prompt.py -v
```

Expected: FAIL with `TypeError: build_summary_prompt() got an unexpected keyword argument 'date_label'` (and similar).

- [ ] **Step 3: Update `build_summary_prompt`**

In `backend/app/services/summary_prompt.py`:

Replace the `build_summary_prompt` signature line:

```python
def build_summary_prompt(
    *,
    today_label: str,
```

with:

```python
def build_summary_prompt(
    *,
    date_label: str,
```

Then replace the `today_label` reference inside the function body:

```python
    sections: list[str] = [_SYSTEM_RULES, f"Today's date: {today_label}"]
```

with:

```python
    sections: list[str] = [_SYSTEM_RULES, f"Today's date: {date_label}"]
```

Also update the docstring line that says `"today_label" is the date string...` to say `"date_label" is the date string...`.

Then replace the news rendering block:

```python
    if news:
        lines = []
        for n in news:
            head = f"- {n.title}"
            if n.description:
                head += f" — {n.description}"
            if n.url:
                head += f" [{n.url}]"
            lines.append(head)
        sections.append("Today's news (raw):\n" + "\n".join(lines))
    else:
        sections.append("Today's news: (none)")
```

with:

```python
    if news:
        lines = []
        for n in news:
            head = f"- {n.title}"
            if n.url:
                head += f" [{n.url}]"
            lines.append(head)
        sections.append("Today's news (raw):\n" + "\n".join(lines))
    else:
        sections.append("Today's news: (none)")
```

(Description rendering removed; `NewsItem.description` stays on the dataclass for back-compat.)

- [ ] **Step 4: Update the call site in `summary_service.py`**

In `backend/app/services/summary_service.py`, inside `_generate_one_for_user`, replace:

```python
    prompt = build_summary_prompt(
        today_label=today_label,
        interests_text=interest_text,
        recent_scores=score_signals_from_rows(recent_scores),
        news=news_items_from_rows(news_rows),
    )
```

with:

```python
    prompt = build_summary_prompt(
        date_label=today_label,
        interests_text=interest_text,
        recent_scores=score_signals_from_rows(recent_scores),
        news=news_items_from_rows(news_rows),
    )
```

(The local variable `today_label` keeps its name because it semantically *is* "today" for the user-triggered path; only the keyword on the prompt builder changes.)

- [ ] **Step 5: Run; verify all summary_prompt + summary_service tests pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_summary_prompt.py tests/unit/test_summary_service.py tests/integration/test_summary_maintenance.py tests/integration/test_summary_pipeline.py -v
```

Expected: pass. The `test_summary_maintenance.py` integration tests still assert old behavior (placeholders etc.) — they should still pass since we haven't yet rewritten `run_bulk_for_all_users`.

- [ ] **Step 6: Stop here for user review/commit.**

---

## Task 7: Add `_previous_day_window` + `_users_with_interests` helpers

**Files:**
- Modify: `backend/app/services/summary_service.py`
- Test: `backend/tests/unit/test_summary_helpers.py` (new)

These pure helpers are easy to test before wiring them into the bulk path.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_summary_helpers.py`:

```python
"""Unit tests for the pure helpers added to summary_service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.services.summary_service import _previous_day_window, _users_with_interests


def test_previous_day_window_returns_yesterday_full_utc_day_and_iso_label():
    now = datetime(2026, 6, 6, 3, 0, 0, tzinfo=UTC)
    start, end, label = _previous_day_window(now)

    assert start == datetime(2026, 6, 5, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 6, 5, 23, 59, 59, tzinfo=UTC)
    assert label == "2026-06-05"


def test_previous_day_window_handles_first_of_month():
    now = datetime(2026, 7, 1, 3, 0, 0, tzinfo=UTC)
    start, end, label = _previous_day_window(now)
    assert start == datetime(2026, 6, 30, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)
    assert label == "2026-06-30"


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
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_summary_helpers.py -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the helpers to `summary_service.py`**

In `backend/app/services/summary_service.py`, near the existing helper functions (`_total_pages`, `_as_utc`), add:

```python
def _previous_day_window(now: datetime) -> tuple[datetime, datetime, str]:
    """Return (yesterday_start, yesterday_end, date_label) for a given run time.

    `now` is expected to be timezone-aware UTC; we use the UTC-day calendar.
    """
    today_midnight = datetime(now.year, now.month, now.day, tzinfo=UTC)
    start = today_midnight - timedelta(days=1)
    end = start + timedelta(hours=23, minutes=59, seconds=59)
    return start, end, start.strftime("%Y-%m-%d")


def _users_with_interests(users, interests) -> list[tuple[int, str]]:
    """Returns (user_id, interests_text) for users whose latest interests row is non-empty.

    Users with no interests row, or an empty/whitespace `interests` field, are excluded.
    Order mirrors `users.list_all_ids()`.
    """
    out: list[tuple[int, str]] = []
    for uid in users.list_all_ids():
        row = interests.get_latest_for_user(uid)
        if row is None:
            continue
        text = (row.interests if hasattr(row, "interests") else getattr(row, "text", None)) or ""
        text = text.strip()
        if not text:
            continue
        out.append((uid, text))
    return out
```

Note: the helper reads `row.interests` to match the real `InterestRepository` row, falling back to `row.text` so the fake repo in tests (which uses `text` field for clarity) also works.

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_summary_helpers.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 8: Rewrite `SummaryMaintenanceService.run_bulk_for_all_users` + ctor + dependencies wiring + integration tests

This is the central task. It changes the bulk pipeline shape, the constructor signature, the dependency-injection wiring, and the integration tests in one atomic change so the codebase stays runnable throughout.

**Files:**
- Modify: `backend/app/services/summary_service.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/tests/integration/test_summary_maintenance.py`

- [ ] **Step 1: Rewrite the integration tests to assert new behavior**

Replace the entire content of `backend/tests/integration/test_summary_maintenance.py` with:

```python
"""Integration tests for the rewritten daily news pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import Interest, User, NewsArticle
from app.repositories.summary_repository import SummaryRepository
from app.services.gdelt_service import GdeltFetcherService, GdeltFetchError
from app.services.summary_service import (
    MockSummaryService,
    SummaryMaintenanceService,
    insert_generated_summary_for_user,
    run_summary_generation_for_all_users,
)


@dataclass
class _CountingFetcher:
    """Stand-in for `GdeltFetcherService` — records calls, returns a configured count."""

    return_count: int = 0
    raise_error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def fetch_and_store(self, *, query: str, start, end) -> int:
        self.calls.append({"query": query, "start": start, "end": end})
        if self.raise_error is not None:
            raise self.raise_error
        return self.return_count


@dataclass
class _StubKeywordExtractor:
    response: str | None
    calls: list[list[tuple[int, str]]] = field(default_factory=list)

    def extract(self, users_with_interests: list[tuple[int, str]]) -> str | None:
        self.calls.append(list(users_with_interests))
        return self.response


@dataclass
class _StubCandidateFilter:
    """Returns the first `top_n` articles unchanged (deterministic ordering for tests)."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def pick_top(self, *, interests_text: str, articles: list[NewsArticle], top_n: int):
        self.calls.append(
            {"interests_text": interests_text, "n_in": len(articles), "top_n": top_n}
        )
        return articles[:top_n]


@dataclass
class _StubSummarizer:
    """Returns the prompt back wrapped so tests can introspect; or raises on demand."""

    raise_error: Exception | None = None
    seen_prompts: list[str] = field(default_factory=list)

    def generate(self, *, prompt: str) -> str:
        self.seen_prompts.append(prompt)
        if self.raise_error is not None:
            raise self.raise_error
        return f"## Daily summary — wired\n\nbody for: {prompt[:30]}..."


def _add_interest(db: Session, user_id: int, text: str) -> None:
    db.add(Interest(user_id=user_id, interests=text))
    db.commit()


def test_users_without_interests_are_skipped(db: Session, user: User):
    other = User(google_id="g2", email="b@example.com")
    db.add(other)
    db.commit()
    _add_interest(db, user.id, "AI, robotics")  # only `user` has interests

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=_CountingFetcher(return_count=0),
        keyword_extractor=_StubKeywordExtractor(response="(AI OR robotics)"),
        candidate_filter=_StubCandidateFilter(),
        telegram_sender=None,
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["users_total"] == 2
    assert stats["users_processed"] == 1
    assert stats["skipped_no_interests"] == 1
    assert SummaryRepository(db).count_for_user(user.id) == 1
    assert SummaryRepository(db).count_for_user(other.id) == 0


def test_when_no_users_have_interests_keyword_extractor_and_gdelt_are_not_called(
    db: Session, user: User
):
    fetcher = _CountingFetcher()
    extractor = _StubKeywordExtractor(response="never used")

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=fetcher,
        keyword_extractor=extractor,
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["users_processed"] == 0
    assert stats["skipped_no_interests"] == 1
    assert fetcher.calls == []
    assert extractor.calls == []


def test_keyword_extractor_returning_none_skips_gdelt_but_still_calls_digest(
    db: Session, user: User
):
    _add_interest(db, user.id, "AI")
    fetcher = _CountingFetcher()

    summarizer = _StubSummarizer()
    svc = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=fetcher,
        keyword_extractor=_StubKeywordExtractor(response=None),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["keyword_extraction_failed"] == 1
    assert fetcher.calls == []
    # User with interests still gets a digest call (with empty news → "_No fresh news today._" body).
    assert stats["users_processed"] == 1
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_gdelt_fetch_error_is_swallowed_and_run_continues(db: Session, user: User):
    _add_interest(db, user.id, "AI")
    fetcher = _CountingFetcher(raise_error=GdeltFetchError("boom"))

    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(),
        gdelt_fetcher=fetcher,
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["gdelt_articles_fetched"] == 0
    assert stats["users_processed"] == 1


def test_user_with_interests_but_digest_failure_is_skipped_with_no_row(
    db: Session, user: User
):
    from app.services.llm_service import LLMError

    _add_interest(db, user.id, "AI")
    svc = SummaryMaintenanceService(
        db,
        summarizer=_StubSummarizer(raise_error=LLMError("boom")),
        gdelt_fetcher=_CountingFetcher(),
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    stats = svc.run_bulk_for_all_users()

    assert stats["digest_failed"] == 1
    assert stats["users_processed"] == 0
    assert SummaryRepository(db).count_for_user(user.id) == 0


def test_date_label_passed_to_prompt_is_yesterday(db: Session, user: User):
    _add_interest(db, user.id, "AI")
    summarizer = _StubSummarizer()
    svc = SummaryMaintenanceService(
        db,
        summarizer=summarizer,
        gdelt_fetcher=_CountingFetcher(),
        keyword_extractor=_StubKeywordExtractor(response="(AI)"),
        candidate_filter=_StubCandidateFilter(),
    )
    svc.run_bulk_for_all_users()

    expected_yesterday = (datetime.now(UTC).date() - __import__("datetime").timedelta(days=1))
    assert any(
        f"Today's date: {expected_yesterday.isoformat()}" in p for p in summarizer.seen_prompts
    )


# Preserved tests for unrelated helpers
def test_insert_generated_summary_for_user_returns_one(db: Session, user: User):
    assert insert_generated_summary_for_user(db, user.id) == 1
    db.commit()
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_run_summary_generation_for_all_users_reports_counts(db: Session, user: User):
    stats = run_summary_generation_for_all_users(db)
    db.commit()
    assert stats["users"] == 1
    assert stats["rows_inserted"] == 1


def test_mock_summary_service_returns_sample_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=1, page_size=5)
    assert resp.total > 0
    assert len(resp.items) == 5
    assert resp.generated_at is not None


def test_mock_summary_service_clamps_high_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=999, page_size=10)
    assert resp.page == resp.total_pages
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_summary_maintenance.py -v
```

Expected: failures from missing constructor params / removed `fetcher` keyword / new stats keys not present.

- [ ] **Step 3: Rewrite `SummaryMaintenanceService` in `summary_service.py`**

In `backend/app/services/summary_service.py`:

3a. **Update imports.** Remove:

```python
from app.services.news_service import NewsFetchError, NewsFetcherService
```

Add (near the other service imports):

```python
from app.core.config import settings
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.gdelt_service import GdeltFetchError, GdeltFetcherService
from app.services.keyword_extractor import KeywordExtractor
```

3b. **Replace `SummaryMaintenanceService.__init__`.** Find:

```python
    def __init__(
        self,
        session: Session,
        *,
        summarizer: LLMSummarizer | None = None,
        fetcher: NewsFetcherService | None = None,
        telegram_sender: TelegramSender | None = None,
    ) -> None:
        self._session = session
        self._summarizer = summarizer
        self._fetcher = fetcher
        self._telegram_sender = telegram_sender
```

Replace with:

```python
    def __init__(
        self,
        session: Session,
        *,
        summarizer: LLMSummarizer | None = None,
        gdelt_fetcher: GdeltFetcherService | None = None,
        keyword_extractor: KeywordExtractor | None = None,
        candidate_filter: PerUserCandidateFilter | None = None,
        telegram_sender: TelegramSender | None = None,
    ) -> None:
        self._session = session
        self._summarizer = summarizer
        self._gdelt_fetcher = gdelt_fetcher
        self._keyword_extractor = keyword_extractor
        self._candidate_filter = candidate_filter
        self._telegram_sender = telegram_sender
```

3c. **Replace `run_bulk_for_all_users` entirely** with:

```python
    def run_bulk_for_all_users(self) -> dict[str, int]:
        """Nightly job entry point: GDELT-based, demand-driven, previous-day digest per user."""
        now = datetime.now(UTC)
        y_start, y_end, date_label = _previous_day_window(now)

        users_repo = UserRepository(self._session)
        interests_repo = InterestRepository(self._session)
        scores_repo = ScoreRepository(self._session)
        news_repo = NewsRepository(self._session)
        summaries_repo = SummaryRepository(self._session)
        transports = TransportService(self._session)

        all_user_ids = users_repo.list_all_ids()
        users_with_interests = _users_with_interests(users_repo, interests_repo)
        skipped_no_interests = len(all_user_ids) - len(users_with_interests)

        stats: dict[str, int] = {
            "users_total": len(all_user_ids),
            "users_processed": 0,
            "skipped_no_interests": skipped_no_interests,
            "digest_failed": 0,
            "gdelt_articles_fetched": 0,
            "keyword_extraction_failed": 0,
            "telegram_sent": 0,
            "telegram_skipped_no_config": 0,
            "telegram_failed": 0,
            "telegram_no_sender": 0,
        }

        if not users_with_interests:
            self._session.commit()
            return stats

        query: str | None = None
        if self._keyword_extractor is not None:
            query = self._keyword_extractor.extract(users_with_interests)
            if query is None:
                stats["keyword_extraction_failed"] = 1

        if query is not None and self._gdelt_fetcher is not None:
            try:
                stats["gdelt_articles_fetched"] = self._gdelt_fetcher.fetch_and_store(
                    query=query,
                    start=y_start.replace(tzinfo=None),
                    end=y_end.replace(tzinfo=None),
                )
            except GdeltFetchError as exc:
                logger.warning("GDELT fetch failed; continuing with stored articles: %s", exc)

        pool = news_repo.list_in_window(
            start=y_start.replace(tzinfo=None),
            end=y_end.replace(tzinfo=None),
            limit=settings.gdelt_max_articles,
        )

        for user_id, interests_text in users_with_interests:
            if self._candidate_filter is not None and pool:
                filtered = self._candidate_filter.pick_top(
                    interests_text=interests_text,
                    articles=pool,
                    top_n=settings.per_user_digest_limit,
                )
            else:
                filtered = pool[: settings.per_user_digest_limit]

            recent_scores = scores_repo.list_recent_for_user(user_id, limit=RECENT_SCORES_LIMIT)
            prompt = build_summary_prompt(
                date_label=date_label,
                interests_text=interests_text,
                recent_scores=score_signals_from_rows(recent_scores),
                news=news_items_from_rows(filtered),
            )
            if self._summarizer is None:
                stats["digest_failed"] += 1
                continue
            try:
                body = self._summarizer.generate(prompt=prompt)
            except LLMError as exc:
                logger.warning("Digest LLM failed for user_id=%s: %s", user_id, exc)
                stats["digest_failed"] += 1
                continue

            summaries_repo.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
            outcome = _deliver_to_telegram(
                user_id=user_id,
                body=body,
                transports=transports,
                sender=self._telegram_sender,
            )
            stats[f"telegram_{outcome}"] += 1
            stats["users_processed"] += 1

        self._session.commit()
        return stats
```

3d. **Update the unused-name check.** The `_components` helper is now unused; delete it. Same for `TelegramOutcome` type alias — no, that one is still used by `_deliver_to_telegram`. Leave it.

3e. **Verify `append_placeholder_for_user` still imports cleanly.** It still uses `_components` indirectly? Re-read: it currently calls `self._components()` to get the five repos. After deleting `_components`, that method breaks. So we need to keep `_components` OR inline it.

Easiest: **keep `_components`** and just remove the `fetcher` import / usage. Replace the deletion of `_components` with: leave it as-is. (It's only used by `append_placeholder_for_user`.)

So step 3d is: leave `_components` alone.

- [ ] **Step 4: Update `api/dependencies.py`**

In `backend/app/api/dependencies.py`:

4a. Replace the imports block (top of file) — remove:

```python
from app.services.news_service import NewsFetcherService
```

Add:

```python
from app.services.candidate_filter import PerUserCandidateFilter
from app.services.gdelt_service import GdeltFetcherService
from app.services.keyword_extractor import KeywordExtractor
```

4b. Replace `_build_news_fetcher`. Find:

```python
def _build_news_fetcher(db: Session) -> NewsFetcherService | None:
    """Returns a configured NewsAPI fetcher, or None when the API key is unset."""
    if not settings.news_api_key.strip():
        return None
    return NewsFetcherService(
        db,
        api_key=settings.news_api_key,
        page_size=settings.news_fetch_limit,
    )
```

Replace with:

```python
def _build_gdelt_fetcher(db: Session) -> GdeltFetcherService:
    """Returns a GDELT fetcher. No API key needed; GDELT is always enabled."""
    return GdeltFetcherService(
        db,
        max_articles=settings.gdelt_max_articles,
        max_records_per_request=settings.gdelt_request_max_records,
    )


def _build_keyword_extractor() -> KeywordExtractor | None:
    """Returns a keyword extractor wrapping the configured summarizer, or None when unconfigured."""
    summarizer = _build_summarizer()
    if summarizer is None:
        return None
    return KeywordExtractor(
        summarizer,
        max_query_chars=settings.keyword_extractor_max_query_chars,
    )


def _build_candidate_filter() -> PerUserCandidateFilter | None:
    """Returns a per-user filter wrapping the configured summarizer, or None when unconfigured."""
    summarizer = _build_summarizer()
    if summarizer is None:
        return None
    return PerUserCandidateFilter(
        summarizer,
        batch_size=settings.per_user_filter_batch,
        top_per_batch=settings.per_user_filter_top_per_batch,
    )
```

4c. Replace `get_summary_maintenance_service`. Find:

```python
def get_summary_maintenance_service(
    db: Annotated[Session, Depends(get_db)],
) -> SummaryMaintenanceService:
    return SummaryMaintenanceService(
        db,
        summarizer=_build_summarizer(),
        fetcher=_build_news_fetcher(db),
        telegram_sender=_build_telegram_sender(),
    )
```

Replace with:

```python
def get_summary_maintenance_service(
    db: Annotated[Session, Depends(get_db)],
) -> SummaryMaintenanceService:
    return SummaryMaintenanceService(
        db,
        summarizer=_build_summarizer(),
        gdelt_fetcher=_build_gdelt_fetcher(db),
        keyword_extractor=_build_keyword_extractor(),
        candidate_filter=_build_candidate_filter(),
        telegram_sender=_build_telegram_sender(),
    )
```

- [ ] **Step 5: Update `scheduler.py` to use new injection names**

In `backend/app/scheduler.py`, replace the imports:

```python
from app.api.dependencies import (
    _build_news_fetcher,
    _build_summarizer,
    _build_telegram_sender,
)
```

with:

```python
from app.api.dependencies import (
    _build_candidate_filter,
    _build_gdelt_fetcher,
    _build_keyword_extractor,
    _build_summarizer,
    _build_telegram_sender,
)
```

And inside `_nightly_summary_job`, replace:

```python
        maintenance = SummaryMaintenanceService(
            db,
            summarizer=_build_summarizer(),
            fetcher=_build_news_fetcher(db),
            telegram_sender=_build_telegram_sender(),
        )
```

with:

```python
        maintenance = SummaryMaintenanceService(
            db,
            summarizer=_build_summarizer(),
            gdelt_fetcher=_build_gdelt_fetcher(db),
            keyword_extractor=_build_keyword_extractor(),
            candidate_filter=_build_candidate_filter(),
            telegram_sender=_build_telegram_sender(),
        )
```

(The cron-hour change comes in Task 10.)

- [ ] **Step 6: Run the full integration + unit suite to verify**

```bash
cd backend && .venv/bin/python -m pytest tests/integration tests/unit -v
```

Expected: all pass. If a stale import to `NewsFetcherService` lingers anywhere, the error will surface here.

- [ ] **Step 7: Stop here for user review/commit.**

---

## Task 9: Update `/tasks/summary/run-bulk` test for new stats shape

**Files:**
- Modify: `backend/tests/api/test_tasks_api.py`

- [ ] **Step 1: Replace `test_runs_with_correct_secret` to assert new stats keys**

In `backend/tests/api/test_tasks_api.py`, find:

```python
def test_runs_with_correct_secret(client: TestClient, monkeypatch, db, user):
    monkeypatch.setattr(settings, "summary_job_secret", "right")
    resp = client.post("/tasks/summary/run-bulk", headers={"x-summary-job-secret": "right"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["users"] == 1
    assert body["rows_inserted"] == 1
```

Replace with:

```python
def test_runs_with_correct_secret(client: TestClient, monkeypatch, db, user):
    monkeypatch.setattr(settings, "summary_job_secret", "right")
    resp = client.post("/tasks/summary/run-bulk", headers={"x-summary-job-secret": "right"})
    assert resp.status_code == 200
    body = resp.json()
    # New stats shape — users without interests get skipped, so this user is counted in
    # skipped_no_interests (no interests row in the fixture).
    assert body["users_total"] == 1
    assert body["users_processed"] == 0
    assert body["skipped_no_interests"] == 1
    assert "gdelt_articles_fetched" in body
    assert "telegram_sent" in body
```

- [ ] **Step 2: Run the test**

```bash
cd backend && .venv/bin/python -m pytest tests/api/test_tasks_api.py -v
```

Expected: all pass.

- [ ] **Step 3: Stop here for user review/commit.**

---

## Task 10: Move scheduler to 03:00 UTC default + add scheduler test

**Files:**
- Modify: `backend/app/scheduler.py`
- Test: `backend/tests/unit/test_scheduler.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_scheduler.py`:

```python
"""Unit tests for the nightly scheduler wiring — does NOT actually start APScheduler."""

from __future__ import annotations

import pytest

from app.core.config import settings


def test_setup_scheduler_uses_summary_schedule_hour_from_settings(monkeypatch):
    from app import scheduler as sched_module

    monkeypatch.setattr(settings, "enable_summary_nightly_scheduler", True)
    monkeypatch.setattr(settings, "summary_schedule_hour", 3)
    monkeypatch.setattr(settings, "summary_schedule_timezone", "UTC")
    # Ensure no leftover from another test.
    sched_module._scheduler = None

    captured: dict = {}

    class _FakeScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, *, id, replace_existing):
            captured["trigger"] = trigger
            captured["id"] = id
            captured["func"] = func

        def start(self):
            captured["started"] = True

        def shutdown(self, wait):
            captured["shutdown_wait"] = wait

    monkeypatch.setattr(sched_module, "AsyncIOScheduler", _FakeScheduler)
    sched_module.setup_scheduler()

    trigger = captured["trigger"]
    # CronTrigger stores fields; the simplest check is repr() containing "hour='3'".
    assert "hour='3'" in repr(trigger)
    assert captured["started"] is True
    assert captured["id"] == sched_module.SUMMARY_JOB_ID

    sched_module.shutdown_scheduler()


def test_setup_scheduler_noop_when_disabled(monkeypatch):
    from app import scheduler as sched_module

    monkeypatch.setattr(settings, "enable_summary_nightly_scheduler", False)
    sched_module._scheduler = None

    def _explode(*_a, **_kw):
        raise AssertionError("should not construct scheduler when disabled")

    monkeypatch.setattr(sched_module, "AsyncIOScheduler", _explode)

    sched_module.setup_scheduler()  # must not raise
    assert sched_module._scheduler is None
```

- [ ] **Step 2: Run; verify failure**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_scheduler.py -v
```

Expected: FAIL — the cron is currently `hour=0`, so `"hour='3'"` is missing from the trigger repr.

- [ ] **Step 3: Update `scheduler.py`**

In `backend/app/scheduler.py`, replace:

```python
    sched.add_job(
        _nightly_summary_job,
        CronTrigger(hour=0, minute=0, second=0, timezone=tz),
        id=SUMMARY_JOB_ID,
        replace_existing=True,
    )
    sched.start()
    logger.info(
        "Nightly summary scheduler started (cron 00:00, timezone=%s)",
        tz,
    )
```

with:

```python
    hour = settings.summary_schedule_hour
    sched.add_job(
        _nightly_summary_job,
        CronTrigger(hour=hour, minute=0, second=0, timezone=tz),
        id=SUMMARY_JOB_ID,
        replace_existing=True,
    )
    sched.start()
    logger.info(
        "Nightly summary scheduler started (cron %02d:00, timezone=%s)",
        hour,
        tz,
    )
```

- [ ] **Step 4: Run; verify pass**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_scheduler.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Stop here for user review/commit.**

---

## Task 11: Delete `NewsFetcherService`, its tests, and old settings; update `.env.example`

This is the cleanup pass. By now nothing should import `news_service` anymore.

**Files:**
- Delete: `backend/app/services/news_service.py`
- Delete: `backend/tests/unit/test_news_service.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/unit/test_config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Sanity-check no remaining imports**

```bash
cd backend && grep -rn "news_service\|NewsFetcher\|NEWSAPI_SOURCE_TAG\|news_api_key\|news_fetch_limit" app tests
```

Expected: zero matches in `app/`. If any match exists, fix it before deleting the file. (Some matches under `tests/unit/test_news_service.py` itself are fine; that file is about to be deleted.)

- [ ] **Step 2: Delete the files**

```bash
rm backend/app/services/news_service.py
rm backend/tests/unit/test_news_service.py
```

- [ ] **Step 3: Remove old settings**

In `backend/app/core/config.py`, delete the two lines:

```python
    news_api_key: str = ""
    news_fetch_limit: int = 20
```

(and the surrounding comment block referencing NewsAPI's top-headlines fetcher).

- [ ] **Step 4: Remove old config test that references the deleted fields, if any exists**

Search:

```bash
cd backend && grep -n "news_api_key\|news_fetch_limit" tests/unit/test_config.py
```

If found, remove those lines. (Initial `test_config.py` doesn't reference them, so likely nothing to remove.)

- [ ] **Step 5: Update `.env.example`**

In `backend/.env.example`, remove:

```
# NewsAPI.org key (https://newsapi.org). Free tier: 100 requests/day, dev use only.
# The nightly job calls /v2/top-headlines once per run. Leave empty to disable the news fetch step.
# NEWS_API_KEY=
# NEWS_FETCH_LIMIT=20
```

In the same block where the nightly job is described, replace:

```
# Nightly summary job (APScheduler): 00:00 in SUMMARY_SCHEDULE_TIMEZONE (IANA). Set false to disable.
# ENABLE_SUMMARY_NIGHTLY_SCHEDULER=true
# SUMMARY_SCHEDULE_TIMEZONE=UTC
```

with:

```
# Nightly summary job (APScheduler): SUMMARY_SCHEDULE_HOUR:00 in SUMMARY_SCHEDULE_TIMEZONE (IANA).
# Default 03:00 UTC, generating the digest for the previous calendar day. Set false to disable.
# ENABLE_SUMMARY_NIGHTLY_SCHEDULER=true
# SUMMARY_SCHEDULE_HOUR=3
# SUMMARY_SCHEDULE_TIMEZONE=UTC

# GDELT DOC API (https://api.gdeltproject.org). No API key required; free and rate-limited.
# Caps the daily article pool size. Reduce if your LLM provider rate-limits per-user filter calls.
# GDELT_MAX_ARTICLES=2000
# GDELT_REQUEST_MAX_RECORDS=250
# PER_USER_FILTER_BATCH=500
# PER_USER_FILTER_TOP_PER_BATCH=25
# PER_USER_DIGEST_LIMIT=50
# KEYWORD_EXTRACTOR_MAX_QUERY_CHARS=450
```

- [ ] **Step 6: Run the entire test suite**

```bash
cd backend && .venv/bin/python -m pytest -v
```

Expected: all pass. No reference to `news_service` should remain anywhere except in `.git/` history.

- [ ] **Step 7: Stop here for user review/commit.**

---

## Task 12: Final end-to-end sanity

**Files:** none modified.

- [ ] **Step 1: Confirm linting / type-checking is clean**

```bash
cd backend && .venv/bin/python -m ruff check app tests
```

Expected: no errors. Fix any minor issues inline (unused imports, etc.).

- [ ] **Step 2: Verify the `/tasks/summary/run-bulk` endpoint runs without errors against the in-memory DB**

```bash
cd backend && .venv/bin/python -m pytest tests/api/test_tasks_api.py -v
```

Expected: 3 passed.

- [ ] **Step 3: Smoke-run the scheduler wiring (no real schedule fires)**

```bash
cd backend && .venv/bin/python -c "from app.scheduler import setup_scheduler, shutdown_scheduler; setup_scheduler(); shutdown_scheduler(); print('ok')"
```

Expected output: `ok` (no traceback). If `ENABLE_SUMMARY_NIGHTLY_SCHEDULER=false` is set in your `.env`, the function exits early — that's fine.

- [ ] **Step 4: Stop here for user review/commit.**

---

## Done

All three roadmap items are implemented:

1. ✅ Fetch news for the previous day (00:00–23:59 UTC) — via `GdeltFetcherService`.
2. ✅ Generate summaries for every user based on interests and scores — via `PerUserCandidateFilter` + `build_summary_prompt` (unchanged score wiring) + the digest LLM call.
3. ✅ Execute at 03:00 UTC for the previous day — via `summary_schedule_hour=3` default + `_previous_day_window(now)` always targeting yesterday.

The roadmap file (`roadmap.md`) can have its three checkboxes ticked.
