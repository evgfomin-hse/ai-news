# E2E Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Playwright e2e tests covering the three untested user flows — Telegram transport settings, score dislike + comment, and summary pagination.

**Architecture:** Tests drive the real browser UI against the already-running stack (FastAPI + Vite + Postgres). They seed rows and cross-check state through the `/api` proxy exactly like the existing `session-flows.spec.ts`. Because the app already implements every behavior, each new test should pass on first correct run — the verification step confirms green, not a TDD red→green transition. Two shared helpers are added; one transport spec runs serial because all tests share one transport row.

**Tech Stack:** `@playwright/test` (Node 24), the existing `bootstrapSession` / `generateSummary` / `fetchScore` helpers.

---

## Prerequisites for running

The suite auto-starts the backend and Vite via `playwright.config.ts`, but needs:
- Postgres up (`bash backend/db.sh`).
- `backend/.env` with `E2E_BOOTSTRAP_SECRET`, `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `JWT_SECRET`.
- `OPENROUTER_API_KEY` left **unset** so the deterministic placeholder summary path is used.
- One-time: `cd e2e && npm install && npm run install:browsers`.

If `E2E_BOOTSTRAP_SECRET` is unset, the authenticated specs skip cleanly (same guard as `session-flows.spec.ts`) — they do not fail.

---

## Task 1: `clearTransport` helper

**Files:**
- Create: `e2e/tests/helpers/transport.ts`

- [ ] **Step 1: Write the helper**

```ts
import type { BrowserContext } from "@playwright/test";

/**
 * Resets the e2e user's transport to an empty baseline by clearing the bot
 * token. The backend drops both token and chat id when the token is emptied
 * (see backend/app/api/transports.py), so this yields a known clean state.
 * Requires a session cookie (call `bootstrapSession` first).
 */
export async function clearTransport(context: BrowserContext): Promise<void> {
    const res = await context.request.patch("/api/transports", {
        headers: { "Content-Type": "application/json" },
        data: { telegramBotToken: "" },
    });
    if (!res.ok()) {
        throw new Error(
            `PATCH /api/transports (clear) failed: ${res.status()} ${await res.text()}`,
        );
    }
}
```

- [ ] **Step 2: Type-check it compiles**

Run: `cd e2e && npx tsc --noEmit`
Expected: no errors (no test references it yet, but the file must type-check).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/helpers/transport.ts
git commit -m "test(e2e): add clearTransport helper"
```

---

## Task 2: `ensureSummaryCount` helper

**Files:**
- Modify: `e2e/tests/helpers/data.ts` (append a new export)

- [ ] **Step 1: Append the helper to `data.ts`**

Add at the end of the file (keep existing `generateSummary` / `fetchScore`):

```ts
/**
 * Ensures the e2e user has at least `min` summary rows, generating only the
 * shortfall via POST /api/summary/generate. Rows only accumulate, so this keeps
 * a ">= N pages" precondition stable across runs. Returns the resulting total.
 */
export async function ensureSummaryCount(
    context: BrowserContext,
    min: number,
): Promise<number> {
    const readTotal = async (): Promise<number> => {
        const res = await context.request.get(
            "/api/summary?page=1&page_size=1",
        );
        if (!res.ok()) {
            throw new Error(
                `GET /api/summary failed: ${res.status()} ${await res.text()}`,
            );
        }
        const body = (await res.json()) as { total: number };
        return body.total;
    };

    let total = await readTotal();
    while (total < min) {
        const gen = await context.request.post("/api/summary/generate");
        if (!gen.ok()) {
            throw new Error(
                `POST /api/summary/generate failed: ${gen.status()} ${await gen.text()}`,
            );
        }
        total += 1;
    }
    return total;
}
```

- [ ] **Step 2: Type-check it compiles**

Run: `cd e2e && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/helpers/data.ts
git commit -m "test(e2e): add ensureSummaryCount helper"
```

---

## Task 3: Telegram transport spec (serial)

**Files:**
- Create: `e2e/tests/settings-transport.spec.ts`

Selector notes (from `frontend/src/pages/Settings/Settings.tsx`):
- New-token input → placeholder `Paste to replace, or leave empty to clear…`.
- Chat-id input → placeholder `e.g. 123456789`.
- Buttons by accessible name: `save token`, `save chat id`, `test bot`, `clear token`, `send test message`.
- Confirmation/error copy renders in `<pre>` boxes: e.g. `Telegram bot token saved.`, `Chat id saved.`, `Token removed (chat id cleared too).`.
- The chat-id validation error from the backend is surfaced verbatim and contains `must be a numeric`.
- `telegramConfigured` (a real token on file) is observable via the **enabled** state of `Test bot` / `Clear token`; the "Bot token on file" chip text is always present and is NOT a reliable signal.

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from "@playwright/test";
import { bootstrapSession } from "./helpers/bootstrap";
import { clearTransport } from "./helpers/transport";

// All users share one transport row, so these mutate shared state and must not
// run in parallel with each other.
test.describe.configure({ mode: "serial" });

test.describe("settings · telegram transport", () => {
    test.beforeEach(async ({ context, page }) => {
        const outcome = await bootstrapSession(context);
        if (outcome === "missing-client-secret") {
            test.skip(
                true,
                "Set E2E_BOOTSTRAP_SECRET in backend/.env (loaded by e2e/playwright.config.ts).",
            );
        }
        if (outcome === "disabled-on-server") {
            test.skip(
                true,
                "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend and restart it.",
            );
        }
        await clearTransport(context);
        await page.goto("/settings");
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
    });

    test("with no transport, test and send are disabled", async ({ page }) => {
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeDisabled();
        await expect(
            page.getByRole("button", { name: /send test message/i }),
        ).toBeDisabled();
    });

    test("saving a bot token enables test and clear", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();

        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeEnabled();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeEnabled();
    });

    test("non-numeric chat id is rejected", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });

        await page.getByPlaceholder("e.g. 123456789").fill("not-a-number");
        await page.getByRole("button", { name: /save chat id/i }).click();

        await expect(page.getByText(/must be a numeric/i)).toBeVisible({
            timeout: 10_000,
        });
    });

    test("valid chat id saves and survives reload", async ({ page }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByText("Telegram bot token saved."),
        ).toBeVisible({ timeout: 10_000 });

        await page.getByPlaceholder("e.g. 123456789").fill("123456789");
        await page.getByRole("button", { name: /save chat id/i }).click();
        await expect(page.getByText("Chat id saved.")).toBeVisible({
            timeout: 10_000,
        });
        // chatDisplay groups digits in threes: "123 456 789".
        await expect(page.getByText(/123 456 789/)).toBeVisible();

        await page.reload();
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
        await expect(page.getByText(/123 456 789/)).toBeVisible();
    });

    test("clearing the token resets configuration and survives reload", async ({
        page,
    }) => {
        await page
            .getByPlaceholder(/paste to replace/i)
            .fill("123456:fake-e2e-token");
        await page.getByRole("button", { name: /save token/i }).click();
        await expect(
            page.getByRole("button", { name: /clear token/i }),
        ).toBeEnabled({ timeout: 10_000 });

        await page.getByRole("button", { name: /clear token/i }).click();
        await expect(
            page.getByText("Token removed (chat id cleared too)."),
        ).toBeVisible({ timeout: 10_000 });
        await expect(page.getByText(/chat not set/i)).toBeVisible();
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();

        await page.reload();
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole("button", { name: /test bot/i }),
        ).toBeDisabled();
    });
});
```

- [ ] **Step 2: Run the spec and confirm green**

Run: `cd e2e && npx playwright test settings-transport.spec.ts --reporter=list`
Expected: 5 passed (or all skipped if `E2E_BOOTSTRAP_SECRET` is unset — that is acceptable, not a failure).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/settings-transport.spec.ts
git commit -m "test(e2e): cover telegram transport settings"
```

---

## Task 4: Score dislike + comment spec

**Files:**
- Create: `e2e/tests/feedback.spec.ts`

Selector notes (from `frontend/src/pages/Home/Home.tsx`):
- Row opens via accessible name `open summary {id}` (regex).
- Modal is `role="dialog"`; vote buttons `Like` / `Dislike`; close button name `close`.
- Comment textarea has a real label `What did you like or dislike?` → use `getByLabel`.
- Before any vote, the textarea placeholder is `Like or dislike first, then add a comment...`.
- Save status is `role="status"`; reads `Saving…` then `Saved`.
- Description save is debounced 600ms and only persists after a vote is cast.

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from "@playwright/test";
import { bootstrapSession } from "./helpers/bootstrap";
import { fetchScore, generateSummary } from "./helpers/data";

test.describe("authenticated · feedback", () => {
    test.beforeEach(async ({ context }) => {
        const outcome = await bootstrapSession(context);
        if (outcome === "missing-client-secret") {
            test.skip(
                true,
                "Set E2E_BOOTSTRAP_SECRET in backend/.env (loaded by e2e/playwright.config.ts).",
            );
        }
        if (outcome === "disabled-on-server") {
            test.skip(
                true,
                "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend and restart it.",
            );
        }
    });

    test("dislike with a comment persists and survives reload", async ({
        context,
        page,
    }) => {
        const seeded = await generateSummary(context);
        const comment = `e2e dislike ${Date.now()}`;

        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        const row = page.getByRole("button", {
            name: new RegExp(`open summary ${seeded.id}`),
        });
        await row.first().click();

        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();

        // Comment is locked before any vote — the placeholder says so.
        await expect(
            dialog.getByLabel(/what did you like or dislike/i),
        ).toHaveAttribute("placeholder", /like or dislike first/i);

        // Vote Dislike.
        const dislike = dialog.getByRole("button", { name: /^dislike$/i });
        await dislike.click();
        await expect(dislike).toHaveAttribute("aria-pressed", "true");

        // Type a comment; debounced save lands after the vote is cast.
        await dialog.getByLabel(/what did you like or dislike/i).fill(comment);
        await expect(dialog.getByRole("status")).toHaveText(/saved/i, {
            timeout: 10_000,
        });

        // Backend cross-check (independent of the UI).
        const stored = await fetchScore(context, seeded.id);
        expect(stored).not.toBeNull();
        expect(stored?.value).toBe(false);
        expect(stored?.description).toBe(comment);

        // Full reload → state must come from GET /score/{id}.
        await page.reload();
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });
        await page
            .getByRole("button", {
                name: new RegExp(`open summary ${seeded.id}`),
            })
            .first()
            .click();
        const reopened = page.getByRole("dialog");
        await expect(
            reopened.getByRole("button", { name: /^dislike$/i }),
        ).toHaveAttribute("aria-pressed", "true");
        await expect(
            reopened.getByLabel(/what did you like or dislike/i),
        ).toHaveValue(comment);
    });
});
```

- [ ] **Step 2: Run the spec and confirm green**

Run: `cd e2e && npx playwright test feedback.spec.ts --reporter=list`
Expected: 1 passed (or skipped if secret unset).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/feedback.spec.ts
git commit -m "test(e2e): cover dislike vote with comment persistence"
```

---

## Task 5: Pagination spec

**Files:**
- Create: `e2e/tests/pagination.spec.ts`

Selector notes (from `frontend/src/pages/Home/Home.tsx`):
- Pager buttons: `← PREV` and `NEXT →` → match by `/prev/i` and `/next/i`.
- Footer text reads `Page {page} of {total_pages} · {total} total …` → match `/page 1 of/i`.
- Real pagination is verified by comparing the first row's accessible name
  (`Open summary {id}: …`) across pages — page 1 and page 2 must differ.
- `PAGE_SIZE = 6`, so `ensureSummaryCount(context, 7)` guarantees ≥2 pages.

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from "@playwright/test";
import { bootstrapSession } from "./helpers/bootstrap";
import { ensureSummaryCount } from "./helpers/data";

test.describe("authenticated · pagination", () => {
    test.beforeEach(async ({ context }) => {
        const outcome = await bootstrapSession(context);
        if (outcome === "missing-client-secret") {
            test.skip(
                true,
                "Set E2E_BOOTSTRAP_SECRET in backend/.env (loaded by e2e/playwright.config.ts).",
            );
        }
        if (outcome === "disabled-on-server") {
            test.skip(
                true,
                "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend and restart it.",
            );
        }
    });

    test("PREV/NEXT page through the feed", async ({ context, page }) => {
        await ensureSummaryCount(context, 7);

        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        const prev = page.getByRole("button", { name: /prev/i });
        const next = page.getByRole("button", { name: /next/i });

        // Page 1: PREV disabled, NEXT enabled.
        await expect(page.getByText(/page 1 of/i)).toBeVisible();
        await expect(prev).toBeDisabled();
        await expect(next).toBeEnabled();

        const firstRow = page.getByRole("button", { name: /open summary/i });
        const page1Top = await firstRow.first().getAttribute("aria-label");

        // Go to page 2.
        await next.click();
        await expect(page.getByText(/page 2 of/i)).toBeVisible({
            timeout: 10_000,
        });
        await expect(prev).toBeEnabled();
        const page2Top = await firstRow.first().getAttribute("aria-label");
        expect(page2Top).not.toBe(page1Top);

        // Back to page 1.
        await prev.click();
        await expect(page.getByText(/page 1 of/i)).toBeVisible({
            timeout: 10_000,
        });
        await expect(prev).toBeDisabled();
    });
});
```

- [ ] **Step 2: Run the spec and confirm green**

Run: `cd e2e && npx playwright test pagination.spec.ts --reporter=list`
Expected: 1 passed (or skipped if secret unset).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/pagination.spec.ts
git commit -m "test(e2e): cover summary feed pagination"
```

---

## Task 6: Full-suite check and docs

**Files:**
- Modify: `e2e/README.md` (extend the "Test layout" list)

- [ ] **Step 1: Run the whole suite**

Run: `cd e2e && npx playwright test --reporter=list`
Expected: all specs pass (or skip cleanly when the bootstrap secret is unset). No failures.

- [ ] **Step 2: Update the Test layout section in `e2e/README.md`**

Add these three bullets under the existing `tests/...` entries:

```markdown
- `tests/settings-transport.spec.ts` — Telegram transport panel: token save,
  chat-id validation, persistence, disabled states (serial; shares one
  transport row). Excludes the live-Telegram "Test bot"/send paths.
- `tests/feedback.spec.ts` — dislike vote + comment: lock-before-vote,
  debounced save, backend cross-check, survives reload
- `tests/pagination.spec.ts` — feed PREV/NEXT pager and disabled states
  (seeds ≥7 rows via `ensureSummaryCount`)
```

And add to the helpers description:

```markdown
- `tests/helpers/transport.ts` — `clearTransport` resets the transport row to an
  empty baseline (used by the serial transport spec)
```

- [ ] **Step 3: Commit**

```bash
git add e2e/README.md
git commit -m "docs(e2e): document transport, feedback, pagination specs"
```

---

## Self-review notes

- **Spec coverage:** Transport (Task 3) → token save / chat-id validation /
  persistence / disabled states. Dislike + comment (Task 4). Pagination
  (Task 5). Helpers `clearTransport` (Task 1) and `ensureSummaryCount` (Task 2)
  match the spec. README update (Task 6) matches the spec's file list.
- **Parallel safety:** Task 3 uses serial mode for the shared transport row;
  Tasks 4–5 seed their own rows (additive, safe under `fullyParallel`).
- **No external deps:** No test calls the live Telegram API or the LLM; saved
  fake tokens are never sent anywhere.
