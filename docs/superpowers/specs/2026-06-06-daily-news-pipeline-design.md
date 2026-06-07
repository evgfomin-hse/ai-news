# Daily news pipeline — previous-day digest at 03:00 UTC

Status: spec — 2026-06-06

## Goal

Deliver the three items in `roadmap.md`:

1. Fetch news for the **previous day** (00:00–23:59 UTC).
2. Generate one digest per user using their **interests** and **scores on previous summaries**.
3. Run the job every day at **03:00 UTC** for the previous day.

The pipeline is **demand-driven**: the news we fetch is the union of what current users actually care about. If no user is interested in politics, we never fetch politics.

## Background

Today the project runs a nightly summary job at 00:00 UTC against NewsAPI `/v2/top-headlines`. That endpoint has no date filtering, returns whatever is current at request time, and doesn't scale to "thousands of articles". The free NewsAPI Developer plan caps `/v2/everything` results at the first 100 per query, making true previous-day breadth impossible.

This spec replaces the NewsAPI fetch with **GDELT DOC API**, which is free, updates every ~15 minutes, supports keyword + date-range queries, and has generous rate limits. We pay for that with the loss of NewsAPI's `description` field; the digest prompt is adjusted to work from title + URL only.

## Architecture

```
03:00 UTC tick
   │
   ▼
KeywordExtractor (1 LLM call)
   • Input: all users + their latest interests
   • Output: GDELT query string "(kw1 OR kw2 OR ...)" capped at ~450 chars
   │
   ▼
GdeltFetcherService (N HTTP calls)
   • Calls /api/v2/doc/doc, mode=ArtList, maxrecords=250
   • Time-slice pagination across yesterday's UTC window
   • Stops at gdelt_max_articles (default 2000)
   • Stores rows in news_articles (description=NULL)
   │
   ▼
for each user with non-empty interests:
   ├─ PerUserCandidateFilter (chunked LLM calls)
   │     • Splits day's pool into batches of per_user_filter_batch (default 500)
   │     • Each batch: LLM picks top per_user_filter_top_per_batch (default 25) indices
   │     • Merges, dedupes by URL, returns first per_user_digest_limit (default 50)
   │
   ├─ Digest LLM call (existing build_summary_prompt)
   │     • prompt: interests + recent 10 scores + 50 filtered articles (title + URL only)
   │     • date_label = yesterday
   │
   ├─ insert summaries row (created_at = job run time)
   │
   └─ Telegram delivery (existing TelegramSender)
```

### What is reused unchanged

- `LLMSummarizer` / `OpenRouterSummarizer` and its dependency wiring.
- `SummaryRepository`, `UserRepository`, `InterestRepository`, `ScoreRepository`, `TransportService`.
- `RequestsTelegramSender` and the `_deliver_to_telegram` helper.
- `POST /tasks/summary/run-bulk` (header-secret-gated manual trigger).
- Score-based personalization: the digest prompt still receives the user's 10 most recent `Score` rows.
- User-triggered `POST /summary/generate` (`append_placeholder_for_user` → `_generate_one_for_user`): uses today's `date_label` (`now.strftime("%Y-%m-%d")`) and the existing rolling 36h news window via `NewsRepository.list_since`. It does **not** trigger a GDELT fetch. Its `build_summary_prompt` call site updates the keyword from `today_label=` to `date_label=` but the value it passes is still "today".

### What is removed

- `NewsFetcherService` (NewsAPI top-headlines) and its tests.
- `_build_news_fetcher` in `api/dependencies.py`.
- `news_api_key`, `news_fetch_limit` settings and their `.env.example` entries.

`NEWS_FRESHNESS_HOURS` (36h) stays — only the **bulk** job stops using it (bulk uses an explicit `yesterday_start`/`yesterday_end` window). The user-triggered "regenerate now" path continues to read the rolling 36h window from `news_articles`.

## Data model & date semantics

### `news_articles`

No DDL change. GDELT-sourced rows store:

| Column | Value |
|---|---|
| `source` | `"gdelt:doc"` |
| `title` | GDELT `title` field |
| `description` | `NULL` (GDELT doesn't provide a snippet) |
| `url` | GDELT `url` field |
| `published_at` | parsed from GDELT `seendate` |
| `fetched_at` | job run time (naive UTC) |

Deduplication by `url` happens inside the fetcher before insert; existing rows with the same URL are not re-inserted.

### Previous-day window

Job runs at 03:00 UTC on day D.

- `yesterday_start = datetime(D.year, D.month, D.day, tzinfo=UTC) - timedelta(days=1)` → `(D − 1) 00:00:00 UTC`.
- `yesterday_end = yesterday_start + timedelta(hours=23, minutes=59, seconds=59)` → `(D − 1) 23:59:59 UTC`.
- GDELT params: `startdatetime=(D-1)YYYYMMDD000000`, `enddatetime=(D-1)YYYYMMDD235959`.
- `date_label = (D - 1).strftime("%Y-%m-%d")` — passed to `build_summary_prompt` so the digest H2 header reads `## Daily summary — YYYY-MM-DD` for yesterday.

### `summaries`

No DDL change. `created_at` remains the job run time (so rows sort correctly by recency). The `date_label` is embedded inside the markdown body, not in a column.

## Components

### `KeywordExtractor` — `backend/app/services/keyword_extractor.py` (new)

```python
class KeywordExtractor:
    def __init__(self, summarizer: LLMSummarizer, *, max_query_chars: int = 450) -> None: ...
    def extract(self, users_with_interests: list[tuple[int, str]]) -> str | None: ...
```

- Filters out empty interests inside the call. If the filtered list is empty → returns `None`.
- Builds a system prompt: "You are extracting search keywords for a news API. Given several users' free-text interests, return a JSON object `{\"global_query_keywords\": [...]}` with deduplicated keywords/phrases that, when OR-joined, will surface news any of these users would care about. Limit to ~25 keywords."
- Calls `summarizer.generate(prompt=...)`, parses JSON. On `LLMError`, JSON parse error, or empty list → returns `None` (logged warning, not raised).
- Dedupes case-insensitively, preserves order, joins with `" OR "`, wraps in `(...)`, truncates at `max_query_chars`. Returns the final query string.

### `GdeltFetcherService` — `backend/app/services/gdelt_service.py` (new)

```python
class GdeltFetchError(RuntimeError): ...

class GdeltFetcherService:
    GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    SOURCE_TAG = "gdelt:doc"

    def __init__(
        self,
        session: Session,
        *,
        max_articles: int = 2000,
        max_records_per_request: int = 250,
        http_get=requests.get,
    ) -> None: ...

    def fetch_and_store(
        self,
        *,
        query: str,
        start: datetime,
        end: datetime,
    ) -> int: ...
```

- Performs **time-slice pagination**: GDELT DOC has no `page` parameter, so we walk the window. Initial request uses `[start, end]`. If response has `len(articles) == max_records_per_request`, the window is narrowed to `[start, oldest_seen_at - 1s]` and the next request runs. Stop when `len(articles) < max_records_per_request`, total stored ≥ `max_articles`, or the window collapses.
- Dedupes by `url` against rows already inserted **in the current call** (in-memory set). Cross-day duplicates against pre-existing `news_articles` are tolerated (cheap; URL collisions across days are rare for our pool size).
- HTTP params: `query`, `mode=ArtList`, `format=json`, `maxrecords=<size>`, `startdatetime`, `enddatetime`, `sort=DateDesc`, `sourcelang=eng`.
- Errors:
  - `requests.RequestException` → `GdeltFetchError("Could not reach GDELT")`.
  - Non-JSON body → `GdeltFetchError("GDELT returned non-JSON")`.
  - HTTP status ≥ 400 → `GdeltFetchError("GDELT: HTTP <code>")`.
- Caller in `summary_service.py` wraps `fetch_and_store` in a try/except `GdeltFetchError`, logs a warning, and continues with whatever was stored (matching today's NewsAPI failure handling).
- Returns the number of rows inserted.

### `PerUserCandidateFilter` — `backend/app/services/candidate_filter.py` (new)

```python
class PerUserCandidateFilter:
    def __init__(
        self,
        summarizer: LLMSummarizer,
        *,
        batch_size: int = 500,
        top_per_batch: int = 25,
    ) -> None: ...

    def pick_top(
        self,
        *,
        interests_text: str,
        articles: list[NewsArticle],
        top_n: int = 50,
    ) -> list[NewsArticle]:
        """Return up to `top_n` articles ranked by LLM-judged relevance to interests."""
```

- Splits `articles` into batches of `batch_size` (preserving original order, which is `fetched_at` desc from the repository).
- For each batch: build a prompt listing the user's `interests_text` and the batch articles as `0. <title>`, `1. <title>`, etc. Ask the LLM to return JSON `{"indices": [..]}` with up to `top_per_batch` indices, most relevant first.
- On `LLMError` or JSON parse error for a batch: log warning, treat that batch as contributing nothing.
- Merge: collect picked articles in batch-order; dedupe by `url`; take the first `top_n`.
- If every batch failed (`picked` is empty): fall back to first `top_n` of `articles` (which is `fetched_at` desc — the most recent).
- Returns the picked list; tracks number of failed batches via an injected counter callback (used by the summary service to surface stats).

### `SummaryMaintenanceService.run_bulk_for_all_users` — modified

New constructor parameter `gdelt_fetcher: GdeltFetcherService | None` (replaces `fetcher`). New parameter `keyword_extractor: KeywordExtractor | None`. New parameter `candidate_filter: PerUserCandidateFilter | None`. All `None`-tolerant so unit tests can supply only what they need.

New helpers (module-level, kept in `summary_service.py`):

```python
def _previous_day_window(now: datetime) -> tuple[datetime, datetime, str]:
    """Return (yesterday_start, yesterday_end, date_label) for a given run time."""

def _users_with_interests(
    users: UserRepository,
    interests: InterestRepository,
) -> list[tuple[int, str]]:
    """Returns (user_id, interests_text) for users whose latest interests row is non-empty.

    Users with no interests row, or an empty/whitespace `interests` field, are excluded.
    """
```

Bulk run becomes:

```python
def run_bulk_for_all_users(self) -> dict[str, int]:
    now = datetime.now(UTC)
    y_start, y_end, date_label = _previous_day_window(now)

    users_repo, interests_repo, scores_repo, news_repo, summaries_repo, transports = self._components()
    users_with_interests = _users_with_interests(users_repo, interests_repo)
    skipped_no_interests = len(users_repo.list_all_ids()) - len(users_with_interests)

    stats = {
        "users_total": len(users_repo.list_all_ids()),
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

    query = None
    if self._keyword_extractor is not None:
        query = self._keyword_extractor.extract(users_with_interests)
        if query is None:
            stats["keyword_extraction_failed"] = 1

    if query is not None and self._gdelt_fetcher is not None:
        try:
            stats["gdelt_articles_fetched"] = self._gdelt_fetcher.fetch_and_store(
                query=query, start=y_start, end=y_end,
            )
        except GdeltFetchError as exc:
            logger.warning("GDELT fetch failed; continuing with stored articles: %s", exc)

    pool = news_repo.list_in_window(start=y_start, end=y_end, limit=settings.gdelt_max_articles)

    for user_id, interests_text in users_with_interests:
        # Filter
        if self._candidate_filter is not None and pool:
            filtered = self._candidate_filter.pick_top(
                interests_text=interests_text,
                articles=pool,
                top_n=settings.per_user_digest_limit,
            )
        else:
            filtered = pool[: settings.per_user_digest_limit]

        # Digest
        recent_scores = scores_repo.list_recent_for_user(user_id, limit=RECENT_SCORES_LIMIT)
        prompt = build_summary_prompt(
            date_label=date_label,
            interests_text=interests_text,
            recent_scores=score_signals_from_rows(recent_scores),
            news=news_items_from_rows(filtered),
        )
        try:
            body = self._summarizer.generate(prompt=prompt)
        except LLMError as exc:
            logger.warning("Digest LLM failed for user_id=%s: %s", user_id, exc)
            stats["digest_failed"] += 1
            continue  # Skip this user entirely. No row, no Telegram.

        summaries_repo.append_row(user_id=user_id, summary=body, created_at=naive_utc_now())
        outcome = _deliver_to_telegram(
            user_id=user_id, body=body, transports=transports, sender=self._telegram_sender,
        )
        stats[f"telegram_{outcome}"] += 1
        stats["users_processed"] += 1

    self._session.commit()
    return stats
```

Notes:
- Removed `today_label`, `llm_generated`/`llm_fallbacks`, `rows_inserted` from stats. Renamed `users` → `users_total`. Added `users_processed`, `skipped_no_interests`, `digest_failed`, `gdelt_articles_fetched`, `keyword_extraction_failed`.
- Placeholder-only code path (`run_summary_generation_for_all_users`, `_placeholder_body`, `BODY_TEMPLATE`, `EMPTY_NOTICE` for an empty no-news state) stays as the user-facing "no summaries yet" notice in `PostgresSummaryService` — that is a UI-empty-state concern and unrelated. The internal `_append_placeholder_row` / `_placeholder_body` helpers used only by the bulk job and by `insert_generated_summary_for_user` can stay (still used by the user-triggered manual trigger when `summarizer is None`); the bulk path simply no longer calls them.

### `build_summary_prompt` — modified, `services/summary_prompt.py`

- Rename keyword arg `today_label` → `date_label`. Both call sites must be updated: the bulk path in `SummaryMaintenanceService.run_bulk_for_all_users` (passes yesterday) and the user-triggered path in `_generate_one_for_user` (passes today).
- `NewsItem`: keep the `description` field on the dataclass for backwards-compat with the user-triggered path (which still has descriptions from any pre-existing NewsAPI rows in `news_articles`). The prompt no longer renders it. Lines become `- {title} [{url}]` (description segment removed).
- System rules header phrasing unchanged otherwise. The H2 rule keeps `## Daily summary — <date_label>`.

### Scheduler — `scheduler.py`

- Cron changes from hardcoded `hour=0, minute=0` to `hour=settings.summary_schedule_hour, minute=0`.
- Default `summary_schedule_hour = 3`.
- `summary_schedule_timezone` default remains `"UTC"`.
- Log message updated to print actual hour.

### Config — `core/config.py`

Added:

```python
summary_schedule_hour: int = 3
gdelt_max_articles: int = 2000
gdelt_request_max_records: int = 250
per_user_filter_batch: int = 500
per_user_filter_top_per_batch: int = 25
per_user_digest_limit: int = 50
keyword_extractor_max_query_chars: int = 450
```

Removed: `news_api_key`, `news_fetch_limit`. `.env.example` updated accordingly: NewsAPI block deleted, GDELT block added explaining it requires no key.

### `api/dependencies.py` — modified

- Delete `_build_news_fetcher`.
- Add `_build_gdelt_fetcher(db)` returning a `GdeltFetcherService` with config-driven params (no API key gate; GDELT is always enabled).
- Add `_build_keyword_extractor()` returning `KeywordExtractor(summarizer)` when a summarizer exists, else `None`.
- Add `_build_candidate_filter()` returning `PerUserCandidateFilter(summarizer)` when a summarizer exists, else `None`.
- `get_summary_maintenance_service` wires all four.

### Repository — `news_repository.py`

Add:

```python
def list_in_window(self, *, start: datetime, end: datetime, limit: int) -> list[NewsArticle]:
    """Articles whose published_at (falling back to fetched_at when NULL) is in [start, end]."""
```

Keep `list_since` for callers in the user-triggered path that still want the rolling window.

## Error handling

Failure policy is **best-effort, skip on user-level failure**:

| Failure point | Behavior |
|---|---|
| No users in DB | Exit early with `users_total=0`. No LLM/HTTP calls. |
| User has no interests row, or interests is empty/whitespace | Skip the user. No `summaries` row, no Telegram, no LLM calls for them. Counted as `skipped_no_interests`. |
| All users have no interests | Skip `KeywordExtractor` + GDELT entirely. Job returns with `users_processed=0`. |
| `KeywordExtractor` LLM call fails or returns empty | `keyword_extraction_failed=1`. Skip GDELT fetch. Pool = whatever's already stored for yesterday's window (likely empty on a fresh run). Per-user digests will produce the prompt's "_No fresh news today._" body for users with interests. |
| `GdeltFetchError` mid-fetch | Log warning. Partial inserts kept. Continue. |
| GDELT returns 0 articles | Pool is empty. Each user's digest produces the "_No fresh news today._" body. Not a failure. |
| `PerUserCandidateFilter` LLM fails on some batches | Those batches contribute 0; surviving batches still produce candidates. Not surfaced in stats. |
| `PerUserCandidateFilter` LLM fails on **all** batches | Fall back to first `per_user_digest_limit` from pool ordered by `fetched_at` desc. Not surfaced in stats. |
| Per-user digest LLM error | **Skip the user** — no summaries row inserted, no Telegram. `digest_failed` incremented. |
| Telegram delivery error | Existing: log, count, do not fail the summary insert. |
| DB error mid-job | Existing: rollback, log exception, scheduler logs failure. Partial rows from earlier in the loop are not rolled back — the commit happens once at the end (matches today's behavior). |

No retries are added by this work. Manual recovery for a missed day goes through `POST /tasks/summary/run-bulk`, which always runs against "yesterday relative to now" — out of scope to add a date parameter here.

## Testing strategy

Backend tests are `pytest`. Coverage targets per new/changed component:

### Unit tests (new)

- `tests/services/test_keyword_extractor.py`
  - Empty input list → returns `None`, no LLM call.
  - All-empty interests filtered out → returns `None`.
  - Valid LLM JSON response → returns `(kw1 OR kw2 OR ...)` deduped, case-insensitive.
  - LLM raises `LLMError` → returns `None`, logs warning.
  - LLM returns malformed JSON → returns `None`.
  - LLM returns empty keyword list → returns `None`.
  - Output query length is capped at `max_query_chars`.

- `tests/services/test_gdelt_service.py`
  - Builds GET with correct `query`, `startdatetime`, `enddatetime`, `mode=ArtList`, `format=json`, `maxrecords`, `sort=DateDesc`, `sourcelang=eng`.
  - Parses one-page ArtList JSON into `NewsArticle` rows; `source` is `"gdelt:doc"`, `description` is `None`, `published_at` parsed from `seendate`.
  - Dedupes by URL inside a single fetch.
  - Time-slice pagination: returns one full page, then a partial page; second request's `enddatetime` equals oldest seen on page 1 minus 1s.
  - Stops at `max_articles` even if more would be available.
  - HTTP error → `GdeltFetchError("Could not reach GDELT")`.
  - HTTP 500 → `GdeltFetchError("GDELT: HTTP 500")`.
  - Non-JSON body → `GdeltFetchError("GDELT returned non-JSON")`.
  - Inserts 0 when response has no `articles` array.

- `tests/services/test_candidate_filter.py`
  - 800 articles → chunks into batches of 500 then 300; two LLM calls.
  - Each batch returns top-25 indices; final list dedupes by URL across batches.
  - Returns first `top_n` preserving batch order for ties.
  - One batch raises `LLMError` → other batches' picks survive.
  - All batches raise → fallback to first `top_n` of input.
  - Empty input → returns empty list, no LLM call.
  - LLM returns out-of-range or non-integer indices → those are dropped, valid ones kept.

- `tests/services/test_summary_prompt.py` (extend existing)
  - `date_label` appears in H2.
  - Description on `NewsItem` is ignored even when set — output lines are `- {title} [{url}]`.

### Unit tests (extend `tests/services/test_summary_service.py`)

- Users without interests rows are skipped: no `summaries` insert, no Telegram, `skipped_no_interests` counted.
- Users with whitespace-only interests are skipped.
- `KeywordExtractor` returning `None` → `gdelt_fetcher.fetch_and_store` not called; `keyword_extraction_failed=1`.
- `GdeltFetcherService.fetch_and_store` raising → run continues; `gdelt_articles_fetched=0`.
- Per-user digest LLM error → that user is skipped: no row inserted, `digest_failed` incremented, Telegram not attempted for them.
- `date_label` passed to `build_summary_prompt` equals `(now − 1 day).strftime("%Y-%m-%d")`.
- `news_repo.list_in_window` is called with `start = (now − 1 day) 00:00 UTC` and `end = (now − 1 day) 23:59:59 UTC`.
- Stats dict shape matches the spec table above.
- `PerUserCandidateFilter` returning a filtered slice → `news_items_from_rows(filtered)` is what `build_summary_prompt` sees.

### Scheduler + config

- `tests/test_scheduler.py` — cron job uses `hour=settings.summary_schedule_hour`; default is 3; timezone wiring unchanged.
- `tests/test_config.py` — new fields present with documented defaults; old `news_api_key`/`news_fetch_limit` absent.

### API

- `tests/api/test_tasks.py` — `/tasks/summary/run-bulk` still returns the new stats dict shape end-to-end with mocked LLM + mocked HTTP.

### Repository

- `tests/repositories/test_news_repository.py` — `list_in_window` returns articles whose `published_at` is in window; falls back to `fetched_at` when `published_at` is NULL; respects `limit`.

### Deletions

- `tests/services/test_news_service.py` deleted (file removed alongside `NewsFetcherService`).

### Manual / e2e

- No `e2e/` changes. The summaries list UI is unaffected; only the *content* of rows changes.
- Manual smoke: run `POST /tasks/summary/run-bulk` with a valid `X-Summary-Job-Secret`, inspect logs and `summaries` table for one expected row per user with interests.

## Out of scope

- Backfilling past days. The job only ever targets "yesterday relative to now". Manual one-off runs of `/tasks/summary/run-bulk` use the same window.
- Embeddings-based ranking for the per-user filter.
- Article body scraping to recover descriptions.
- Source diversification beyond GDELT (RSS, NewsAPI hybrid). Easy to add later as a second fetcher.
- Catching up after a missed scheduler firing — APScheduler's `misfire_grace_time` defaults are kept.
- UI changes to expose the new stats.
