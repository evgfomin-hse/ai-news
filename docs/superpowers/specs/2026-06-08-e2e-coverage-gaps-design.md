# E2E coverage gaps — design

**Date:** 2026-06-08
**Status:** Approved

## Goal

Close the three untested user-flow gaps in the Playwright e2e suite, keeping
every test deterministic and free (no live Telegram bot, no LLM). The new tests
follow the existing suite's conventions: drive the real browser UI, seed rows
and cross-check state through the API, use selector-based assertions (no
screenshot baselines), and stay idempotent against the shared e2e user.

## Background

The e2e user is shared and its rows persist across runs (see `e2e/README.md`).
Existing tests stay parallel-safe by seeding their own summary rows and using
`Date.now()` markers. `playwright.config.ts` runs `fullyParallel: true`.

Already covered (`guest.spec.ts`, `session-flows.spec.ts`): guest landing +
router guard, home render, interests save/reload, score "like" persistence,
logout, unknown-route fallback, CSV export.

## Scope

In scope — three gaps, all deterministic:

1. **Telegram transport settings** — save token, chat-id validation, persistence.
2. **Score dislike + comment** — the dislike vote and description flow.
3. **Summary pagination** — the PREV/NEXT pager and disabled states.

Explicitly out of scope (require a live Telegram API, not deterministic):
"Test bot" success path, the hello-capture polling, and real message sending.

## Files

| File | Change |
|---|---|
| `e2e/tests/settings-transport.spec.ts` | New, `test.describe.serial` |
| `e2e/tests/feedback.spec.ts` | New |
| `e2e/tests/pagination.spec.ts` | New |
| `e2e/tests/helpers/data.ts` | Extend with `ensureSummaryCount(context, min)` |
| `e2e/tests/helpers/transport.ts` | New, `clearTransport(context)` |

All authenticated specs reuse `bootstrapSession` in `beforeEach` and skip
cleanly when `E2E_BOOTSTRAP_SECRET` is unset, matching `session-flows.spec.ts`.

## Helpers

### `helpers/transport.ts` — `clearTransport(context)`

`PATCH /api/transports` with `{ telegramBotToken: "" }`. The backend clears both
token and chat id when the token is emptied (`api/transports.py`), giving each
serial transport test a known empty baseline. Throws on non-OK responses.

### `helpers/data.ts` — `ensureSummaryCount(context, min)`

Reads `total` from `GET /api/summary?page=1&page_size=1`, then calls the
existing `generateSummary` path until `total >= min`. Returns the final total.
Because rows only accumulate, this keeps the ≥2-page precondition true across
runs while seeding only what's missing.

## Test specs

### 1. `settings-transport.spec.ts` (serial)

`test.describe.serial` — all users share one transport row, so parallel
mutation would race. `beforeEach`: `bootstrapSession` (+ skip guard) then
`clearTransport` for a clean baseline.

- **Save bot token:** fill "New token", click "Save token" → "Telegram bot token
  saved." visible; chip reads "Bot token on file"; "Test bot" and "Clear token"
  become enabled.
- **Reject non-numeric chat id:** with a token on file, enter `not-a-number`,
  click "Save chat id" → error box shows the backend 400 detail
  (`telegramChatId must be a numeric…`).
- **Save valid chat id + persist:** enter `123456789`, save → "Chat id saved.";
  chip shows the space-grouped chat id; reload → chip still shows it.
- **Clear token + persist:** click "Clear token" → "Token removed (chat id
  cleared too)."; chip back to "chat not set"; reload → still cleared.
- **Disabled states:** after `clearTransport`, "Test bot", "Clear token", and
  "Send test message" are disabled (no token/chat).

### 2. `feedback.spec.ts`

Seeds its own summary via `generateSummary` (parallel-safe). Opens the modal by
its `open summary {id}` accessible label.

- Comment textarea is locked before any vote — placeholder contains
  "Like or dislike first".
- Click **Dislike** → `aria-pressed="true"`; type a comment → debounced save →
  status reads "Saved".
- Backend cross-check via `fetchScore`: `value === false`,
  `description === comment`.
- Reload → reopen modal → Dislike still `aria-pressed="true"` and the comment
  text is restored from `GET /score/{id}`.

### 3. `pagination.spec.ts`

`ensureSummaryCount(context, 7)` guarantees ≥2 pages (`PAGE_SIZE = 6`).

- Page 1: "← PREV" disabled, "NEXT →" enabled, footer shows "Page 1 of N".
- Click NEXT → footer shows page 2, "← PREV" enabled, first row number is `#07`.
- Click PREV → back to page 1, "← PREV" disabled again.

## Testing

The specs are the tests. Validation = the suite passes locally with a running
backend + Postgres and `E2E_BOOTSTRAP_SECRET` set, and skips cleanly when it
isn't. `OPENROUTER_API_KEY` stays unset so the placeholder summary path is what
assertions run against.
