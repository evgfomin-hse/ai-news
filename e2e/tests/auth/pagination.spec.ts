import { expect, test } from "@playwright/test";
import { bootstrapSession } from "../helpers/bootstrap";
import { ensureSummaryCount } from "../helpers/data";

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
