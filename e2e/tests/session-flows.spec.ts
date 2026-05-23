import { expect, test } from "@playwright/test";
import { bootstrapSession } from "./helpers/bootstrap";
import { fetchScore, generateSummary } from "./helpers/data";

test.describe("authenticated", () => {
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
                "API returned 404 for bootstrap: set E2E_BOOTSTRAP_SECRET on the backend process and restart it.",
            );
        }
    });

    test("home renders with masthead and header chrome", async ({ page }) => {
        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });
        await expect(
            page.getByRole("link", { name: /ai news home/i }),
        ).toBeVisible();
        await expect(
            page.getByRole("link", { name: /^settings$/i }),
        ).toBeVisible();
        await expect(
            page.getByRole("button", { name: /^logout$/i }),
        ).toBeVisible();
    });

    test("interests save and survive a reload", async ({ page }) => {
        const marker = `e2e-${Date.now()}`;

        await page.goto("/settings");
        await expect(
            page.getByRole("heading", { name: /^settings$/i }),
        ).toBeVisible({ timeout: 10_000 });

        const interests = page.getByPlaceholder(/machine learning/i);
        await interests.fill(marker);
        await page.getByRole("button", { name: /save interests/i }).click();
        await expect(page.getByText("Interests saved.")).toBeVisible({
            timeout: 10_000,
        });

        await page.reload();
        await expect(page.getByPlaceholder(/machine learning/i)).toHaveValue(
            marker,
        );
    });

    test("score persists across modal reopen and full reload", async ({
        context,
        page,
    }) => {
        // Seed a fresh summary so this test owns the top row of the feed.
        const seeded = await generateSummary(context);

        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        // Open the newest summary by its accessible label (set in Home.tsx:268).
        const row = page.getByRole("button", {
            name: new RegExp(`open summary ${seeded.id}`),
        });
        await row.first().click();

        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        await expect(
            dialog.getByRole("heading", { name: seeded.title }),
        ).toBeVisible();

        // Vote Like and wait for the inline status to confirm persistence.
        const like = dialog.getByRole("button", { name: /^like$/i });
        await like.click();
        await expect(like).toHaveAttribute("aria-pressed", "true");
        await expect(dialog.getByRole("status")).toHaveText(/saved/i, {
            timeout: 10_000,
        });

        // Backend has the row (cross-checks the PUT path independently of the UI).
        const stored = await fetchScore(context, seeded.id);
        expect(stored).not.toBeNull();
        expect(stored?.value).toBe(true);

        // Reopen → state served from in-memory cache, still pressed.
        await dialog.getByRole("button", { name: /^close$/i }).click();
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await row.first().click();
        await expect(
            page
                .getByRole("dialog")
                .getByRole("button", { name: /^like$/i }),
        ).toHaveAttribute("aria-pressed", "true");

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
        await expect(
            page
                .getByRole("dialog")
                .getByRole("button", { name: /^like$/i }),
        ).toHaveAttribute("aria-pressed", "true");
    });

    test("logout clears the session and returns to Login", async ({ page }) => {
        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        await page.getByRole("button", { name: /^logout$/i }).click();

        await expect(
            page.getByRole("heading", { name: /stay up to date/i }),
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole("button", { name: /^logout$/i }),
        ).toHaveCount(0);
    });

    test("unknown route falls back to home for authed users", async ({
        page,
    }) => {
        await page.goto("/no-such-route");
        // App.tsx catches "*" and Navigate to="/" replaces it.
        await expect(page).toHaveURL(/\/$/);
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });
    });

    test("CSV export downloads a non-empty file with a dated filename", async ({
        context,
        page,
    }) => {
        // Make sure the e2e user has at least one row so EXPORT TO CSV is enabled.
        await generateSummary(context);

        await page.goto("/");
        await expect(
            page.getByRole("heading", { name: /good morning/i }),
        ).toBeVisible({ timeout: 15_000 });

        const button = page.getByRole("button", { name: /export to csv/i });
        await expect(button).toBeEnabled({ timeout: 15_000 });

        const [download] = await Promise.all([
            page.waitForEvent("download"),
            button.click(),
        ]);

        // Server sets Content-Disposition: attachment; filename="summaries-YYYY-MM-DD.csv"
        expect(download.suggestedFilename()).toMatch(
            /^summaries-\d{4}-\d{2}-\d{2}\.csv$/,
        );

        // Sanity-check the body: header row present, at least one data row.
        const path = await download.path();
        const fs = await import("node:fs/promises");
        const content = await fs.readFile(path, "utf-8");
        const lines = content.trim().split("\n");
        expect(lines[0]).toBe(
            "summary_id,created_at_utc,body,score,score_description",
        );
        expect(lines.length).toBeGreaterThanOrEqual(2);
    });
});
