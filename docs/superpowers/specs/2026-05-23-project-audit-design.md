# Project audit — design spec

**Date:** 2026-05-23
**Owner:** evgfomin
**Status:** approved (brainstorming)

## Goal

Produce a single Markdown audit report identifying concrete issues across the **HSE AI News** project (backend, frontend, e2e, docs), so the team can pick which to fix. The audit does **not** fix anything; it inventories findings with file:line citations, severity, and a 1–2 line suggested fix.

## Scope

**In scope (all four areas):**

- **Backend** — `backend/app` (api, services, repositories, models, schemas, scheduler, lifespan, core), plus `backend/tests` (unit, integration, api).
- **Frontend** — `frontend/src` (pages, features, shared/api, shared/ui, main.tsx, App.tsx).
- **E2E** — `e2e/tests`, `e2e/playwright.config.ts`.
- **Docs** — repo-root `README.md` / `README_en.md` (currently describe an unrelated Go tunnel project — known mismatch), `backend/README.md`, `frontend/README.md`, `backend/.env.example`.

**Issue types to flag:**

- Correctness bugs & broken endpoints (wrong status codes, 500 leakage, schema mismatches, race conditions, broken auth)
- Missing HTTP error handling (endpoints that swallow errors or return 500s instead of typed 4xx; missing input validation)
- Test gaps (missing unit / integration / Playwright coverage for specific endpoints or flows; brittle tests)
- Readability, naming, dead code, misleading comments, copy-paste

**Out of scope:**

- Implementing fixes — audit only.
- Running Playwright with real browsers — dev servers will be started, but the browser test run is gated on a separate user OK.
- Touching `.env`, secrets, or database data.
- Architectural rewrites or framework migrations.

## Procedure

Four ordered stages.

### Stage 1 — Verify the project runs

A clean checkout that won't start is the highest-priority finding. Before reading any code, capture the runtime baseline.

1. Start Postgres via `backend/db.sh` (Docker). If a container with that name already exists, reuse it.
2. Set up backend venv manually (do **not** invoke `backend/start.sh` — it deletes the venv and then blocks running uvicorn). Steps: `uv venv --python 3.11 backend/.venv` (or fall back to system python if 3.11 unavailable), `uv pip install -r backend/requirements-dev.txt`.
3. Run `pytest` from `backend/`. Record full pass/fail summary; any failure becomes a Critical finding.
4. Start FastAPI dev server in background (`uvicorn app.main:app --port 8000`) and curl `/openapi.json` + `/health/db`. Stop the server before Stage 4.
5. Run `npm install` in `frontend/` (if `node_modules` is stale), start Vite dev server in background, curl `http://127.0.0.1:5173/`. Stop the server before Stage 4.
6. Run `npm install` in `e2e/` and `npx playwright --version` (do **not** run tests yet).

Each failure here is logged with the exact command, exit code, and first 20 lines of stderr.

### Stage 2 — Map the API surface

With the FastAPI server up, capture the OpenAPI schema and diff it against the frontend API client.

- Pull `GET /openapi.json` and list every route × method × declared response.
- Walk `frontend/src/shared/api/calls/*.ts` and list every call (URL, method, request/response shape).
- Findings: endpoints the frontend calls but server doesn't expose (or vice-versa), shape mismatches between frontend types and OpenAPI schemas, missing 4xx handling on the client (catch blocks that swallow, no toast/UI on error), endpoints the server exposes but nothing consumes (dead code or missing test).

### Stage 3 — Read each module systematically

Order: backend api → services → repositories → schemas; frontend pages → features → shared; e2e tests; READMEs and env example.

For each file, look for:

- **Backend:** endpoints that raise plain exceptions instead of `HTTPException`, status codes that don't match the situation (e.g., 500 where 404/409/422 fits), missing input validation, N+1 queries, unbounded queries, missing pagination caps, auth checks missing or done in the wrong layer, mutations not in transactions, swallowed exceptions, dead imports, misleading docstrings, wrong-language comments, `print` instead of `logger`.
- **Frontend:** components that crash on undefined props, missing loading/error states, fetch calls without error handling, hard-coded URLs, prop drilling that should be context, dead components, type mismatches with backend, accessibility issues that are trivial to spot (missing `aria-label`, `<button>` rendered as `<div>`).
- **E2E:** brittle selectors (text-based when role-based would work), no fixture isolation, tests that depend on order, missing assertions for error paths, missing coverage of core flows visible in the API surface.
- **Tests (pytest):** integration tests masquerading as unit tests, missing teardown, hard-coded waits, tests that pass for the wrong reason (e.g., assert true), gaps revealed by Stage 2 surface map.
- **Docs:** factual errors, broken commands, missing prerequisites, language mismatch (the repo-root READMEs are about a different project entirely).

### Stage 4 — Write the report

Single file: `docs/audit-2026-05-23.md`. Structure:

```
# Audit — 2026-05-23

## Summary
- Counts by severity × area (small table).
- Runtime-baseline status (did backend start, did tests pass, did frontend start).
- Top 3 findings the team should fix this week.

## Critical
C1 — <title>
  File: backend/app/api/foo.py:42
  Found: <1–3 sentences>
  Suggested fix: <1–2 lines, direction only — no code>

C2 — …

## Major
M1 — …

## Minor
m1 — …

## Per-area appendix
### Backend
  - Cross-reference of finding IDs that live in backend/
### Frontend
### E2E
### Docs

## Severity rubric
(verbatim copy of the rubric below)
```

## Severity rubric

- **Critical** — wrong/broken at runtime: 500s where a 4xx is expected, data corruption risk, auth bypass, dev environment won't start, pytest already broken on a clean checkout.
- **Major** — missing HTTP error handling on user-facing endpoints, real bugs in non-critical paths, meaningful test gaps for core flows (login, summary fetch, transports config, score upsert).
- **Minor** — readability, naming, dead code, misleading comments, brittle tests, doc cleanup.

## Finding format (verbatim per entry)

```
<ID> — <one-line title>
  File: <relative path>:<line>
  Found: <1–3 sentences describing the issue and why it matters>
  Suggested fix: <1–2 lines pointing at a direction — no code>
```

Use stable IDs (`C1`, `M3`, `m12`) so the team can reference them in follow-up PRs.

## Deliverables

- `docs/audit-2026-05-23.md` — the audit report.
- This spec, committed to `docs/superpowers/specs/2026-05-23-project-audit-design.md`.

## Non-goals (explicit)

- No fixes applied to `app/`, `src/`, `tests/`, or `e2e/`.
- No new tests written.
- No README rewrites — they're flagged in the audit, not fixed.
- No dependency upgrades.
- No `.env` edits.

## Risks & mitigations

- **Docker / Postgres not running locally** → Stage 1 will fail at step 1. Mitigation: if `docker` isn't available, mark Stage 1 partial, skip to Stage 3, and flag "verify on a machine with Docker" as a top-line caveat in the report.
- **`requirements.txt` install fails** (Python 3.14 in pyproject.toml vs 3.11 in `start.sh` — already a likely finding) → log it as Critical, proceed with whatever Python the venv ends up using.
- **Playwright not gated** → Playwright browser run is **not** part of the procedure unless the user explicitly OKs it after Stage 1. Default: skip.
- **Audit scope creep** → if a finding requires deep investigation (e.g., suspected race condition), log it as "needs investigation" rather than spending an hour confirming it. The audit is breadth-first.

## Success criteria

- One Markdown file at `docs/audit-2026-05-23.md` exists and is committed.
- Every finding has: ID, file:line, ≤3-sentence description, ≤2-line suggested fix, and a severity.
- Summary section makes it possible to triage in under 5 minutes.
- Runtime baseline (Stage 1 result) is visible at the top.
- No code outside `docs/` has been modified.
