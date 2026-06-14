# E2E — HSE AI News

Playwright tests that exercise the full stack (FastAPI + Vite + Postgres).

## Requirements

- Node 24
- A running Postgres (the backend won't start without it — see `backend/db.sh`)
- `backend/.env` with these set:
  - `DATABASE_URL` — Postgres connection string
  - `E2E_BOOTSTRAP_SECRET` — any long random value; enables `POST /auth/e2e/bootstrap-session`
- `GOOGLE_CLIENT_ID` / `JWT_SECRET` — needed for the backend to start, but the bootstrap path bypasses Google sign-in

## One-time setup

```bash
# From repo root
bash backend/db.sh                       # start Postgres if not already up

cd e2e
npm install
npm run install:browsers                 # downloads Chromium for Playwright
```

## Running

```bash
# Headless run (auto-starts backend + frontend per playwright.config.ts)
npm test

# Watch a browser window
npm run test:headed

# Interactive runner / debugger
npm run test:ui
```

The `webServer` config in `playwright.config.ts` starts the FastAPI app
(`python -m uvicorn app.main:app`) on port 8000 and the Vite dev server on
port 5173 before the suite runs, and reuses already-running instances locally.

## Test layout

Specs are split by auth zone: `tests/unauth/` runs without a session,
`tests/auth/` bootstraps a session first. Shared helpers live in `tests/helpers/`.

**Unauthenticated (`tests/unauth/`)**

- `guest.spec.ts` — unauthenticated landing and protected-route guard

**Authenticated (`tests/auth/`)** — each bootstraps a session in `beforeEach`

- `session-flows.spec.ts` — home, interests roundtrip, score persistence
  (vote → cache → reload → server fetch), logout, unknown-route fallback
- `settings-transport.spec.ts` — Telegram transport panel: token save,
  chat-id validation, persistence, disabled states (serial; shares one
  transport row). Excludes the live-Telegram "Test bot"/send paths.
- `pagination.spec.ts` — feed PREV/NEXT pager and disabled states
  (seeds ≥7 rows via `ensureSummaryCount`)

**Helpers (`tests/helpers/`)**

- `bootstrap.ts` — `POST /auth/e2e/bootstrap-session` to mint a real session
  cookie; skips tests cleanly when `E2E_BOOTSTRAP_SECRET` is unset
- `data.ts` — `generateSummary` / `fetchScore` / `ensureSummaryCount` for
  seeding via API so tests don't depend on an LLM being configured (the
  placeholder summary path is deterministic and free)
- `transport.ts` — `clearTransport` resets the transport row to an empty
  baseline (used by the serial transport spec)

## Notes

- The bootstrap endpoint always uses the same e2e user (email
  `e2e-playwright@example.invalid`). State persists across runs — tests are
  written to be idempotent (seed a fresh row when needed, use `Date.now()`
  markers for interests).
- Seeding never calls a real LLM during e2e: the `data.ts` helpers insert rows via
  `POST /summary/import.csv` (the export-format CSV), so a summary row is created
  deterministically regardless of which LLM backend `backend/.env` points at
  (including a local no-key LM Studio) and with no backend restart.
