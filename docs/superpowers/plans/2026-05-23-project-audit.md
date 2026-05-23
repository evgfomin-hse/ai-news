# Project Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/audit-2026-05-23.md` — a single Markdown audit report inventorying concrete issues across backend, frontend, e2e, and docs of the HSE AI News project. Audit only; no fixes.

**Architecture:** Four ordered stages, mapped to tasks. Stage 1 (Tasks 1–5) verifies the project actually runs and captures a runtime baseline. Stage 2 (Task 6) maps the API surface and diffs server vs. client. Stage 3 (Tasks 7–10) reads each module systematically and logs findings into a working scratch file. Stage 4 (Task 11) organizes findings by severity, writes the summary, and finalizes the report.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / PostgreSQL 16 (Docker) / pytest / React 19 / TypeScript / Vite / Playwright / `uv`, `npm`, `curl`, `docker`.

**Working files used by this plan:**

- `docs/audit-2026-05-23-scratch.md` — running scratchpad. Tasks append findings here, freely-formatted. Deleted at the end of Task 11.
- `docs/audit-2026-05-23.md` — final deliverable. Written only in Task 11.

**Operational rules:**

- **No git commits in this plan.** The user commits manually. Skip every "commit" step you might be used to.
- **No fixes.** If something is broken, log it as a finding, do not patch it.
- **Background servers must be stopped before moving on.** Each task that starts a server explicitly stops it.
- **If a verification command fails, that's a finding — don't try to fix it.** Log the exact command, exit code, first 20 lines of stderr to the scratchpad, then continue.

---

## Task 1: Stage 1 — Bring up Postgres and prepare the backend venv

**Files:**

- Read: `backend/db.sh`, `backend/start.sh`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `pyproject.toml`
- Create: `docs/audit-2026-05-23-scratch.md`

- [ ] **Step 1: Initialize the scratchpad**

Write `docs/audit-2026-05-23-scratch.md` with this exact content:

```markdown
# Audit scratchpad — 2026-05-23

This is a working file; the polished report is `docs/audit-2026-05-23.md`. Delete on completion.

## Stage 1 — runtime baseline

## Stage 2 — API surface diff

## Stage 3 — module-by-module findings (raw)

### Backend (api / services / repositories / models / schemas / scheduler / lifespan / core)

### Backend tests (pytest)

### Frontend (pages / features / shared)

### E2E (Playwright)

### Docs & env

## Stage 4 — pending notes (anything not yet classified)
```

- [ ] **Step 2: Start Postgres**

Run: `bash backend/db.sh`
Expected: prints a container ID. If the container `hse-ai-news-postgres` already exists, the command fails with "Conflict. The container name … is already in use" — in that case run `docker start hse-ai-news-postgres` and continue.
Verify: `docker ps --filter name=hse-ai-news-postgres --format '{{.Status}}'` shows `Up ...`.

If `docker` is not installed: append to scratchpad under `## Stage 1 — runtime baseline`:

```
- [CRITICAL] Docker not available on audit machine. Cannot verify db.sh, /health/db, or any DB-dependent test path. Mark every DB-touching finding as "unverified".
```

Then skip the rest of Task 1 and proceed to Task 6 (Stage 2 still works if you can stand up the server with a stub DB — but more likely you'll have to skip Stage 1 results and continue with code reading from Task 7).

- [ ] **Step 3: Create the backend venv (do NOT run `backend/start.sh`)**

`backend/start.sh` deletes `.venv` and then blocks running uvicorn, so we can't use it.

Run, from repo root:
```bash
cd backend && uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python --upgrade pip && uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Expected: venv created, packages installed without error.

If `uv venv --python 3.11` fails because Python 3.11 isn't on the system: re-run with whatever Python `uv` defaults to (`uv venv .venv`), and append to scratchpad:

```
- [MAJOR] start.sh pins Python 3.11 but pyproject.toml requires-python = ">=3.14". Inconsistent. Recommend pick one and align both.
```

- [ ] **Step 4: Record the baseline**

Append to scratchpad under `## Stage 1 — runtime baseline`:

```
- Postgres: <up | not available | reused existing>
- Backend venv: <created with Python X.Y | failed because …>
- pip install -r requirements-dev.txt: <success | failed with: <first error line>>
```

---

## Task 2: Stage 1 — Run pytest, record results

**Files:**

- Run: `cd backend && .venv/bin/python -m pytest -ra` (note: `pytest.ini` already sets `--strict-markers`)
- Append to: `docs/audit-2026-05-23-scratch.md`

- [ ] **Step 1: Run the full backend test suite**

Run:
```bash
cd backend && .venv/bin/python -m pytest -ra --tb=short 2>&1 | tail -200
```

Capture the full short summary section (everything after `==== short test summary info ====` plus the final `passed/failed/skipped` line).

- [ ] **Step 2: Log the result**

Append to scratchpad under `## Stage 1 — runtime baseline`:

```
- pytest: <N passed, M failed, K skipped, T errors in X.YYs>
  - If any failures, list each as: `FAILED tests/path/test_foo.py::test_bar - <reason>`
```

If there are failures, **also** add an entry under `## Stage 3 — module-by-module findings (raw)` → `### Backend tests (pytest)`:

```
- [CRITICAL] pytest fails on a clean checkout. Failing tests: <list>. Investigate before any other backend work.
```

If pytest cannot even start (e.g., import error, missing dep): log the full traceback under Stage 1 and mark as Critical.

---

## Task 3: Stage 1 — Start FastAPI, probe endpoints, stop it

**Files:**

- Run in background: `cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Append to: `docs/audit-2026-05-23-scratch.md`
- Save: `docs/audit-2026-05-23-openapi.json` (used in Task 6)

- [ ] **Step 1: Start the server in background**

Run via Bash tool `run_in_background: true`:
```bash
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait until the server is reachable. Use Monitor or a short polling loop:
```bash
until curl -sf http://127.0.0.1:8000/openapi.json -o /dev/null; do sleep 1; done
```

- [ ] **Step 2: Pull OpenAPI schema for Task 6**

Run: `curl -sf http://127.0.0.1:8000/openapi.json > docs/audit-2026-05-23-openapi.json`
Verify: `jq '.paths | keys | length' docs/audit-2026-05-23-openapi.json` returns a number > 0.

If `jq` not available, fall back to `python -c "import json,sys; d=json.load(open('docs/audit-2026-05-23-openapi.json')); print(len(d['paths']))"`.

- [ ] **Step 3: Hit `/health/db`**

Run: `curl -sS -w '\nHTTP_STATUS:%{http_code}\n' http://127.0.0.1:8000/health/db`
Capture: response body + status code.

- [ ] **Step 4: Hit `/auth/google-login` with a dummy body to confirm error handling**

Run:
```bash
curl -sS -w '\nHTTP_STATUS:%{http_code}\n' \
  -H 'Content-Type: application/json' \
  -d '{"token":"not-a-real-token"}' \
  http://127.0.0.1:8000/auth/google-login
```
Capture: response body + status code. We expect 401 or 503, NOT 500.

- [ ] **Step 5: Stop the background server**

Kill the background bash shell. (Use the `KillShell` tool, or send `SIGTERM` to the shell ID returned from Step 1.)

Verify: `curl -sf http://127.0.0.1:8000/openapi.json` now fails (connection refused).

- [ ] **Step 6: Log results**

Append to scratchpad under `## Stage 1 — runtime baseline`:

```
- FastAPI dev server: <started | failed: …>
- /openapi.json paths count: <N>
- /health/db: HTTP <code>, body: <first line of body>
- /auth/google-login (bad token): HTTP <code>, body: <first line>
```

If any of these returned 500, add a Critical finding to `### Backend` in Stage 3.

---

## Task 4: Stage 1 — Stand up the Vite frontend, probe, stop it

**Files:**

- Run in background: `cd frontend && npm run dev -- --host 127.0.0.1 --strictPort --port 5173`
- Append to: `docs/audit-2026-05-23-scratch.md`

- [ ] **Step 1: Ensure node_modules**

Check `frontend/node_modules/.package-lock.json` exists. If not, run `cd frontend && npm install` first.

- [ ] **Step 2: Start the Vite dev server in background**

Run via Bash tool `run_in_background: true`:
```bash
cd frontend && npm run dev -- --host 127.0.0.1 --strictPort --port 5173
```

Wait for reachability:
```bash
until curl -sf http://127.0.0.1:5173 -o /dev/null; do sleep 1; done
```

- [ ] **Step 3: Fetch root and check shape**

Run: `curl -sS http://127.0.0.1:5173 | head -50`
Confirm an HTML body containing `<div id="root">` (or equivalent — read `frontend/index.html` first to know the expected mount node id).

- [ ] **Step 4: Stop the background server**

Kill the background shell. Verify port is free: `curl -sf http://127.0.0.1:5173` fails.

- [ ] **Step 5: Log results**

Append to scratchpad under `## Stage 1 — runtime baseline`:

```
- Vite dev server: <started | failed: …>
- / responds with HTML containing #root: <yes | no>
- Vite or TS warnings in stdout/stderr worth noting: <list any "type error", "warning", "deprecated">
```

---

## Task 5: Stage 1 — Verify Playwright tooling installs (no test run)

**Files:**

- Run: `cd e2e && npm install && npx playwright --version`
- Append to: `docs/audit-2026-05-23-scratch.md`

- [ ] **Step 1: Install e2e deps**

Run: `cd e2e && npm install`
Capture: any peer-dep warnings, audit warnings.

- [ ] **Step 2: Confirm Playwright CLI**

Run: `cd e2e && npx playwright --version`
Expected: a version string like `Version 1.52.0`.

Do **NOT** run `npx playwright install` (downloads browsers — expensive) or `npx playwright test` (executes tests). That's gated on a separate user OK.

- [ ] **Step 3: Log**

Append to scratchpad under `## Stage 1 — runtime baseline`:

```
- e2e npm install: <success | failed: …>
- Playwright CLI: <version string>
- Browsers NOT installed in this audit — gated on user OK.
```

---

## Task 6: Stage 2 — Map API surface, diff server against frontend client

**Files:**

- Read: `docs/audit-2026-05-23-openapi.json` (from Task 3), `frontend/src/shared/api/client.ts`, `frontend/src/shared/api/api.ts`, every file in `frontend/src/shared/api/calls/`
- Append to: `docs/audit-2026-05-23-scratch.md` under `## Stage 2 — API surface diff`

- [ ] **Step 1: Enumerate server routes**

Parse `docs/audit-2026-05-23-openapi.json` and list every `path × method`. Suggested:
```bash
jq -r '.paths | to_entries[] | .key as $p | .value | to_entries[] | "\(.key|ascii_upcase) \($p)"' docs/audit-2026-05-23-openapi.json | sort
```
Capture: the full list.

- [ ] **Step 2: Enumerate frontend API calls**

Read each file under `frontend/src/shared/api/calls/` (`auth.ts`, `interests.ts`, `summary.ts`, `transports.ts`). For each, record:
- Function name
- HTTP method + URL it calls
- What it does on non-2xx responses (throws? returns null? swallows?)

If a function doesn't handle non-2xx at all, that's a Major finding (record under `### Frontend` in Stage 3, with file:line).

- [ ] **Step 3: Diff**

Build three lists in the scratchpad:

```
**Server-only endpoints (server exposes, frontend never calls):**
- <METHOD /path> — dead code or missing UI?

**Client-only calls (frontend calls, server doesn't expose):**
- <METHOD /path> in <file>:<line> — broken call

**Both sides, but shape mismatch:**
- <METHOD /path> — server returns <X>, frontend expects <Y> (file:line of the TS type)
```

Each mismatch becomes a finding in Stage 3 with appropriate severity (Critical if it would break at runtime, Major if it's a latent bug, minor if just types-vs-runtime drift).

---

## Task 7: Stage 3 — Read the backend systematically; log findings

**Files (read in this order):**

1. `backend/app/main.py`, `backend/app/lifespan.py`, `backend/app/scheduler.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/core/time.py`
2. `backend/app/api/dependencies.py`, then each `backend/app/api/*.py` (`auth.py`, `users.py`, `interests.py`, `summary.py`, `transports.py`, `tasks.py`, `health.py`, `score.py`)
3. `backend/app/services/*.py` (in the same order as their API files)
4. `backend/app/repositories/*.py`
5. `backend/app/models/*.py`
6. `backend/app/schemas/*.py`
7. `backend/tests/conftest.py`, then `backend/tests/unit/*.py`, `backend/tests/integration/*.py`, `backend/tests/api/*.py`

For each file, scan for these patterns and log each hit:

- [ ] **Step 1: HTTP error handling patterns (backend)**

For every endpoint (router function), check:

- Does it raise `HTTPException` for every error path, or does some path return None / raise a generic `Exception` (which becomes a 500)?
- Are the status codes correct? 400 for bad input, 401 for unauthenticated, 403 for unauthorized, 404 for not found, 409 for conflict, 422 for validation, 502 for upstream failure, 503 for service-unavailable.
- Are inputs validated by Pydantic schemas (look at body/query params)? If a regex/range constraint is enforced in the handler instead, that's minor — better in the schema.
- Are `requests.RequestException` / `SQLAlchemyError` / `ValueError` from third-party calls caught and translated to typed HTTPException?

Log each issue in scratchpad under `### Backend` with format:

```
- [SEVERITY] <one-line title> — file:<line> — <1–3 sentence description>. Suggested fix: <1–2 lines>.
```

- [ ] **Step 2: Correctness patterns (backend)**

For every file, also check:

- `app.main`: is `CORSMiddleware` configured safely? (allow_credentials=True + allow_origins=["*"] is a CORS bug, but the code uses `cors_origins_list` — verify the parsing.)
- Endpoints that mutate DB: are they wrapped in transactions? Are commits/rollbacks correct in services?
- Endpoints that hit external services (Telegram, Google): are timeouts set? Are retries reasonable? Are responses validated before use?
- Background tasks (`scheduler.py`): are errors logged? Is the job idempotent?
- Auth (`dependencies.get_current_user`, `auth.google_login`): are tokens validated? Are claims (`sub`, `iat`, `exp`) checked? Is `jwt.decode` using `algorithms=[settings.jwt_algorithm]` (good — it does)? Is the cookie clear/set logic symmetric (same flags on set and delete)?
- N+1 / unbounded queries in repositories.
- Use of `print` instead of `logger`.
- Misleading or wrong-language docstrings.
- Dead imports / unused functions.

Log each issue with file:line, severity, suggested fix.

- [ ] **Step 3: Test patterns (pytest)**

For `backend/tests/`:

- Are unit tests under `tests/unit/` actually unit tests (no DB, no HTTP)? If `tests/unit/test_summary_service.py` touches a real `Session`, that's a misclassification (minor).
- Do integration tests have proper setup/teardown (fixtures, transaction rollback)?
- Are API tests using the FastAPI TestClient? Do they cover the happy path AND at least one error path per endpoint?
- Coverage gaps: cross-reference with the route list from Task 6. Which endpoints have no test at all?
- Tests that pass for the wrong reason (e.g., `assert True`, missing assertions, only checking status code without body).
- Hard-coded sleeps, time.sleep, fragile time assertions (compare with `app/core/time.py`).

Log each issue under `### Backend tests (pytest)` in scratchpad.

- [ ] **Step 4: Sanity check the running notes**

Read your scratchpad and confirm:
- Every finding has a file:line.
- Every finding has a severity ([CRITICAL] / [MAJOR] / [minor]).
- Every finding has a 1–2 line suggested fix.

Fix any entry that's missing one of these.

---

## Task 8: Stage 3 — Read the frontend systematically; log findings

**Files (read in this order):**

1. `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/index.html`
2. `frontend/src/features/Auth/*.tsx`
3. `frontend/src/pages/Login/Login.tsx`, `frontend/src/pages/Home/Home.tsx`, `frontend/src/pages/Settings/Settings.tsx`
4. `frontend/src/shared/ui/Header/Header.tsx`, `frontend/src/shared/ui/StatusBar/StatusBar.tsx`
5. `frontend/src/shared/api/client.ts`, `frontend/src/shared/api/api.ts`, `frontend/src/shared/api/calls/*.ts` (already partially covered in Task 6 — re-read for non-API issues)
6. `frontend/eslint.config.js`, `frontend/vite.config.ts`, `frontend/tsconfig*.json`

For each file, scan for:

- [ ] **Step 1: Error/loading state patterns**

- Components that call the API: do they show a loading indicator? Do they show an error message on failure? Do they render correctly when data is empty / undefined?
- Error boundaries: is there one at the page level? At the app level?
- Components that crash if a prop is undefined (e.g., `user.email.split('@')`).

Log each issue under `### Frontend` in scratchpad with file:line, severity, fix.

- [ ] **Step 2: Auth flow correctness**

- `AuthProvider`: how does it react to a 401 from the API? Does it redirect to /login?
- `OAuthProvider`: is the Google client ID read from env? Is it validated?
- Logout: does it clear local state? Does it call `/auth/logout`?
- Routing: are protected routes actually guarded?

- [ ] **Step 3: TS/React red flags**

- `any` types, especially on API response types.
- `useEffect` with missing dependency arrays.
- State setters called inside render bodies (infinite re-render).
- Inline functions in `useMemo`/`useCallback` deps that defeat memoization.
- Stale closures over state in event handlers.
- Hard-coded API URLs instead of using `client.ts`.
- Dead imports, unused props, commented-out code.
- Accessibility low-hanging fruit: `<div onClick>` instead of `<button>`, images missing `alt`, form inputs missing labels.

- [ ] **Step 4: Sanity check**

Confirm each `### Frontend` finding has file:line + severity + fix. Fix any entry missing one.

---

## Task 9: Stage 3 — Read e2e tests; log findings

**Files:**

1. `e2e/playwright.config.ts`
2. `e2e/tests/guest.spec.ts`
3. `e2e/tests/session-flows.spec.ts`
4. Every file under `e2e/tests/helpers/`

- [ ] **Step 1: Read config and helpers first**

For `playwright.config.ts`:
- Is `webServer.command` correct (uses `python -m uvicorn` directly — fine)?
- Is `reuseExistingServer` configured sensibly? (line 36 already explains the CI string-bool gotcha — verify the comment matches behavior.)
- Are `trace` / `retries` / `workers` set sensibly?
- Are baseURL and project setup minimal? Any missing browsers?

- [ ] **Step 2: Read each spec**

For each `*.spec.ts`:
- Are selectors role-based (`getByRole`, `getByLabel`) or brittle text-based?
- Is there fixture isolation (each test gets a fresh user/session via the `/auth/e2e/bootstrap-session` endpoint)?
- Do tests depend on order? Do they share state via the DB?
- Are there assertions for error paths (e.g., bad bot token → error toast shown)?
- Compare with the route list from Task 6: which user-facing flows have NO e2e coverage at all?

- [ ] **Step 3: Log**

Append to `### E2E (Playwright)` in scratchpad. Same format: file:line, severity, fix.

---

## Task 10: Stage 3 — Read docs / READMEs / env example; log findings

**Files:**

1. `README.md`
2. `README_en.md`
3. `backend/README.md`
4. `frontend/README.md`
5. `backend/.env.example`
6. `LICENSE` (sanity glance only)

- [ ] **Step 1: Repo-root READMEs**

These currently describe a Go tunnel project (`GO Simple Tunnel` / GOST) and have nothing to do with HSE AI News. That's a [CRITICAL] doc issue — log it once under `### Docs & env` with the suggested fix:

```
- [CRITICAL] README.md and README_en.md describe an unrelated project (Go-based GOST tunnel). New users have no real onboarding doc. Suggested fix: replace both with content describing HSE AI News (purpose, stack, dev setup pointing to backend/README + frontend/README + e2e setup).
```

- [ ] **Step 2: backend/README and frontend/README**

Currently minimal (3-step bullet lists). Check:
- Do they list every prerequisite (Python 3.11/3.14? Node 24?)?
- Do the commands actually work as written?
- Is there a pointer to `.env.example`?
- Are env vars documented?

- [ ] **Step 3: `.env.example`**

- Are all referenced settings in `app/core/config.py` represented? Any settings the code reads that aren't documented here (or vice versa)?
- Are placeholder values safe (no real secrets)?
- Are comments accurate?

- [ ] **Step 4: Log**

Append every issue under `### Docs & env` with file:line (where applicable), severity, fix.

---

## Task 11: Stage 4 — Write the final report

**Files:**

- Read: `docs/audit-2026-05-23-scratch.md` (everything accumulated)
- Create: `docs/audit-2026-05-23.md`
- Delete (at the end): `docs/audit-2026-05-23-scratch.md`, `docs/audit-2026-05-23-openapi.json`

- [ ] **Step 1: Read the entire scratchpad**

Open `docs/audit-2026-05-23-scratch.md`. Count findings per severity per area. Build the summary numbers.

- [ ] **Step 2: Assign stable IDs**

Walk every finding in scratchpad in order: Stage 3 backend → backend tests → frontend → e2e → docs. Within each section, walk Critical first, then Major, then minor. Assign IDs:

- Critical: `C1`, `C2`, `C3`, …
- Major: `M1`, `M2`, …
- Minor: `m1`, `m2`, …

(One ID counter per severity, NOT per area. IDs are globally unique.)

- [ ] **Step 3: Write `docs/audit-2026-05-23.md`**

Create the file with this exact structure (replace `<…>` placeholders with real content):

```markdown
# Audit — 2026-05-23

**Project:** HSE AI News (FastAPI + React + PostgreSQL + Playwright)
**Scope:** backend / frontend / e2e / docs
**Method:** four-stage breadth-first audit. Runtime verified, API surface mapped, modules read systematically. No fixes applied.

## Summary

| Severity | Backend | Frontend | E2E | Docs | Total |
|---|---|---|---|---|---|
| Critical | <n> | <n> | <n> | <n> | <n> |
| Major | <n> | <n> | <n> | <n> | <n> |
| Minor | <n> | <n> | <n> | <n> | <n> |

**Runtime baseline (Stage 1):**

- Postgres: <status from scratchpad>
- pytest: <result from scratchpad>
- FastAPI dev server: <result>
- Vite dev server: <result>
- Playwright tooling: <result>

**Top 3 to fix this week:**

1. <finding ID> — <one-line title>
2. <finding ID> — <one-line title>
3. <finding ID> — <one-line title>

(Pick the three highest-impact items, weighing severity × user-facing reach × ease of fix.)

## Critical

### C1 — <title>
- **File:** <path>:<line>
- **Found:** <1–3 sentences>
- **Suggested fix:** <1–2 lines>

### C2 — …

(continue for every Critical finding)

## Major

### M1 — <title>
- **File:** <path>:<line>
- **Found:** …
- **Suggested fix:** …

### M2 — …

## Minor

### m1 — <title>
- **File:** <path>:<line>
- **Found:** …
- **Suggested fix:** …

### m2 — …

## Per-area appendix

### Backend
- C1, M1, M3, m2, m5 (cross-reference of IDs from the backend; one line each with the title)

### Backend tests (pytest)
- …

### Frontend
- …

### E2E (Playwright)
- …

### Docs & env
- …

## Severity rubric

- **Critical** — wrong/broken at runtime: 500s where 4xx is expected, data corruption risk, auth bypass, dev environment won't start, pytest already broken on a clean checkout.
- **Major** — missing HTTP error handling on user-facing endpoints, real bugs in non-critical paths, meaningful test gaps for core flows (login, summary fetch, transports config, score upsert).
- **Minor** — readability, naming, dead code, misleading comments, brittle tests, doc cleanup.

## Method

Stage 1 verified the project starts on a clean checkout. Stage 2 captured the OpenAPI schema and diffed against the frontend API client. Stage 3 read every backend module (api → services → repositories → models → schemas) and every frontend module (pages → features → shared), plus all existing tests and Playwright specs. Stage 4 (this report) organized findings.

No code outside `docs/` was modified during this audit.
```

- [ ] **Step 4: Sanity-check the final report**

Open the report and verify, line by line:

- Every finding has: ID, file:line (or "N/A" only where genuinely none applies, e.g., a missing test), 1–3-sentence description, 1–2-line fix.
- The summary table numbers match the actual count of `### Cn` / `### Mn` / `### mn` headings.
- The per-area appendix lists every finding ID exactly once.
- "Top 3 to fix this week" entries also appear under their Critical/Major section.
- The runtime baseline section is filled in (not left as placeholders).

Fix any issue inline.

- [ ] **Step 5: Clean up scratch files**

Delete:
- `docs/audit-2026-05-23-scratch.md`
- `docs/audit-2026-05-23-openapi.json`

Leave only `docs/audit-2026-05-23.md`.

- [ ] **Step 6: Hand off**

Print a one-line summary to the user:
> "Audit complete: `docs/audit-2026-05-23.md`. <n> Critical / <n> Major / <n> minor findings across <areas>. Runtime baseline: <one-line status>."

Do **not** commit. The user commits manually.

---

## Done

That's the whole plan. After Task 11, `docs/audit-2026-05-23.md` is the deliverable; everything else under `docs/` from this work has been deleted. No source code, tests, or configs outside `docs/` were modified.
